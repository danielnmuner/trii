const CONFIG = Object.freeze({
  API_BASE_URL: 'https://c5jjznedu6.execute-api.us-east-1.amazonaws.com',
  API_TOKEN: 'K4CG63VXRNWP66QVJA4L',
  SPREADSHEET_ID: '1GSRsy-PzcolCP41uPB0ohaOwXpdR-cSYxphNuxN5n9U',

  SENDER_EMAIL: 'notificaciones@fymtech.com',
  SUBJECT_REGEX: /acciones\s+y\s+valores\s+s\.?a\.?\s+comisionistas\s+de\s+bolsa/i,
  BOGOTA_TIMEZONE: 'America/Bogota',

  STATE_SHEET_NAME: 'InvoiceSyncState',
  LOG_SHEET_NAME: 'InvoiceSyncLog',

  LOOKBACK_DAYS: 1,
  THREAD_PAGE_SIZE: 100,
  MAX_ZIP_UPLOADS_PER_RUN: 100,
  MAX_RUNTIME_MS: 5.5 * 60 * 1000,
  API_THROTTLE_MS: 500,

  USER_EMAIL_OVERRIDE: ''
});

const STATE_HEADERS = ['key', 'value', 'updated_at'];

const LOG_HEADERS = [
  'processed_at',
  'status',
  'user_email',
  'gmail_message_date',
  'gmail_message_id',
  'gmail_thread_id',
  'from_email',
  'subject',
  'attachment_name',
  'attachment_key',
  'zip_sha256',
  'zip_size_bytes',
  'archive_stem',
  'xml_file_name',
  'pdf_file_name',
  'api_status_code',
  'api_response_status',
  'api_response_message',
  'api_bucket',
  'uploaded_files',
  'xml_s3_key',
  'pdf_s3_key',
  'error'
];

function syncFymtechInvoicesToTrii() {
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);

  const runStartedAt = new Date();
  const deadline = runStartedAt.getTime() + CONFIG.MAX_RUNTIME_MS;

  let stateSheet;
  let logSheet;
  let lastCommittedAt = null;

  try {
    const spreadsheet = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    stateSheet = ensureSheet_(spreadsheet, CONFIG.STATE_SHEET_NAME, STATE_HEADERS);
    logSheet = ensureSheet_(spreadsheet, CONFIG.LOG_SHEET_NAME, LOG_HEADERS);

    setStateValues_(stateSheet, {
      last_run_started_at: formatDateTimeBogota_(runStartedAt),
      last_run_completed_at: '',
      last_run_status: 'RUNNING',
      last_error: ''
    });

    const userEmail = getCurrentUserEmail_();
    const lastProcessedAt = getLastProcessedAt_(stateSheet, logSheet);
    lastCommittedAt = lastProcessedAt;

    const queryStartDate = buildQueryStartDate_(lastProcessedAt, CONFIG.LOOKBACK_DAYS);
    const processedKeys = loadSuccessfulAttachmentKeys_(logSheet);
    const messages = collectCandidateMessages_(queryStartDate);

    let uploadedCount = 0;
    let skippedCount = 0;
    let scannedMessages = 0;
    let failed = false;
    let partial = false;

    for (let i = 0; i < messages.length; i++) {
      if (Date.now() > deadline) {
        partial = true;
        break;
      }

      if (uploadedCount >= CONFIG.MAX_ZIP_UPLOADS_PER_RUN) {
        partial = true;
        break;
      }

      const message = messages[i];
      const result = processMessage_(message, userEmail, processedKeys, logSheet);

      scannedMessages += 1;
      uploadedCount += result.uploadedCount;
      skippedCount += result.skippedCount;

      if (!result.success) {
        failed = true;
        break;
      }

      lastCommittedAt = message.getDate();
    }

    if (lastCommittedAt) {
      setStateValues_(stateSheet, {
        last_processed_at: formatDateTimeBogota_(lastCommittedAt)
      });
    }

    const finalStatus = failed ? 'FAILED' : (partial ? 'PARTIAL' : 'OK');

    setStateValues_(stateSheet, {
      last_run_completed_at: formatDateTimeBogota_(new Date()),
      last_run_status: finalStatus,
      last_error: failed ? 'See the latest FAILED row in InvoiceSyncLog.' : ''
    });

    const summary = {
      status: finalStatus,
      userEmail: userEmail,
      lastProcessedAt: lastCommittedAt ? formatDateTimeBogota_(lastCommittedAt) : null,
      scannedMessages: scannedMessages,
      uploadedZipAttachments: uploadedCount,
      skippedAlreadyProcessed: skippedCount,
      totalCandidateMessages: messages.length
    };

    Logger.log(JSON.stringify(summary, null, 2));
    return summary;
  } catch (error) {
    if (stateSheet) {
      setStateValues_(stateSheet, {
        last_run_completed_at: formatDateTimeBogota_(new Date()),
        last_run_status: 'FAILED',
        last_error: String(error && error.message ? error.message : error)
      });

      if (lastCommittedAt) {
        setStateValues_(stateSheet, {
          last_processed_at: formatDateTimeBogota_(lastCommittedAt)
        });
      }
    }
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function ensureSheet_(spreadsheet, sheetName, headers) {
  let sheet = spreadsheet.getSheetByName(sheetName);
  if (!sheet) {
    sheet = spreadsheet.insertSheet(sheetName);
  }

  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
    sheet.setFrozenRows(1);
  }

  return sheet;
}

function getCurrentUserEmail_() {
  const override = String(CONFIG.USER_EMAIL_OVERRIDE || '').trim();
  if (override) {
    return override.toLowerCase();
  }

  const activeUserEmail = String(Session.getActiveUser().getEmail() || '').trim();
  if (activeUserEmail) {
    return activeUserEmail.toLowerCase();
  }

  const effectiveUserEmail = String(Session.getEffectiveUser().getEmail() || '').trim();
  if (effectiveUserEmail) {
    return effectiveUserEmail.toLowerCase();
  }

  throw new Error('Could not resolve the current account email. Set CONFIG.USER_EMAIL_OVERRIDE manually.');
}

function getLastProcessedAt_(stateSheet, logSheet) {
  const state = getStateMap_(stateSheet);
  const rawValue = state.last_processed_at;

  if (rawValue) {
    const parsed = new Date(rawValue);
    if (!isNaN(parsed.getTime())) {
      return parsed;
    }
  }

  const rows = getDataRows_(logSheet);
  const statusIndex = LOG_HEADERS.indexOf('status');
  const dateIndex = LOG_HEADERS.indexOf('gmail_message_date');

  let maxTime = null;
  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][statusIndex]) !== 'UPLOADED') {
      continue;
    }
    const parsed = new Date(rows[i][dateIndex]);
    if (isNaN(parsed.getTime())) {
      continue;
    }
    if (maxTime === null || parsed.getTime() > maxTime) {
      maxTime = parsed.getTime();
    }
  }

  return maxTime === null ? null : new Date(maxTime);
}

function buildQueryStartDate_(lastProcessedAt, lookbackDays) {
  if (!lastProcessedAt) {
    return null;
  }
  return new Date(lastProcessedAt.getTime() - lookbackDays * 24 * 60 * 60 * 1000);
}

function collectCandidateMessages_(queryStartDate) {
  const queryParts = [
    'in:all',
    'has:attachment',
    'from:' + CONFIG.SENDER_EMAIL
  ];

  if (queryStartDate) {
    queryParts.push('after:' + formatDateForGmailQuery_(queryStartDate));
  }

  const query = queryParts.join(' ');
  const messages = [];
  const seenMessageIds = {};
  let start = 0;

  while (true) {
    const threads = GmailApp.search(query, start, CONFIG.THREAD_PAGE_SIZE);
    if (!threads.length) {
      break;
    }

    for (let i = 0; i < threads.length; i++) {
      const threadMessages = threads[i].getMessages();
      for (let j = 0; j < threadMessages.length; j++) {
        const message = threadMessages[j];
        const messageId = message.getId();

        if (seenMessageIds[messageId]) {
          continue;
        }
        seenMessageIds[messageId] = true;

        if (!isTargetMessage_(message, queryStartDate)) {
          continue;
        }

        messages.push(message);
      }
    }

    start += threads.length;
    if (threads.length < CONFIG.THREAD_PAGE_SIZE) {
      break;
    }
  }

  messages.sort(function(a, b) {
    const delta = a.getDate().getTime() - b.getDate().getTime();
    if (delta !== 0) {
      return delta;
    }
    return a.getId() < b.getId() ? -1 : 1;
  });

  return messages;
}

function isTargetMessage_(message, queryStartDate) {
  const fromEmail = extractEmailAddress_(message.getFrom());
  if (fromEmail !== CONFIG.SENDER_EMAIL.toLowerCase()) {
    return false;
  }

  const subject = normalizeCellText_(message.getSubject());
  if (!CONFIG.SUBJECT_REGEX.test(subject)) {
    return false;
  }

  if (queryStartDate && message.getDate().getTime() < queryStartDate.getTime()) {
    return false;
  }

  return true;
}

function processMessage_(message, userEmail, processedKeys, logSheet) {
  const attachments = message.getAttachments({
    includeInlineImages: false,
    includeAttachments: true
  });

  const zipAttachments = [];
  for (let i = 0; i < attachments.length; i++) {
    if (isZipAttachment_(attachments[i])) {
      zipAttachments.push(attachments[i]);
    }
  }

  if (!zipAttachments.length) {
    return {
      success: true,
      uploadedCount: 0,
      skippedCount: 0
    };
  }

  let uploadedCount = 0;
  let skippedCount = 0;

  for (let i = 0; i < zipAttachments.length; i++) {
    const attachment = zipAttachments[i];
    const attachmentName = attachment.getName() || ('attachment-' + (i + 1) + '.zip');
    const zipBlob = attachment.copyBlob();
    const zipBytes = zipBlob.getBytes();
    const zipSha256 = sha256Hex_(zipBytes);
    const attachmentKey = [
      message.getId(),
      attachmentName,
      zipSha256
    ].join('|');

    if (processedKeys.has(attachmentKey)) {
      skippedCount += 1;
      continue;
    }

    try {
      const invoiceDocument = buildInvoiceDocumentFromZip_(attachmentName, zipBlob);
      const apiResult = uploadInvoiceDocument_(userEmail, invoiceDocument);

      appendLogRows_(logSheet, [[
        formatDateTimeBogota_(new Date()),
        'UPLOADED',
        userEmail,
        formatDateTimeBogota_(message.getDate()),
        message.getId(),
        message.getThread().getId(),
        extractEmailAddress_(message.getFrom()),
        normalizeCellText_(message.getSubject()),
        attachmentName,
        attachmentKey,
        zipSha256,
        zipBytes.length,
        invoiceDocument.archive_stem,
        invoiceDocument.xml_file_name,
        invoiceDocument.pdf_file_name,
        apiResult.httpStatusCode,
        apiResult.body.status || '',
        apiResult.body.message || '',
        getNestedValue_(apiResult.body, ['result', 'bucket']) || '',
        getNestedValue_(apiResult.body, ['result', 'uploaded_files']) || '',
        getNestedValue_(apiResult.body, ['result', 'documents', 0, 'xml_s3_key']) || '',
        getNestedValue_(apiResult.body, ['result', 'documents', 0, 'pdf_s3_key']) || '',
        ''
      ]]);

      processedKeys.add(attachmentKey);
      uploadedCount += 1;
    } catch (error) {
      appendLogRows_(logSheet, [[
        formatDateTimeBogota_(new Date()),
        'FAILED',
        userEmail,
        formatDateTimeBogota_(message.getDate()),
        message.getId(),
        message.getThread().getId(),
        extractEmailAddress_(message.getFrom()),
        normalizeCellText_(message.getSubject()),
        attachmentName,
        attachmentKey,
        zipSha256,
        zipBytes.length,
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        '',
        truncateText_(String(error && error.message ? error.message : error), 5000)
      ]]);

      return {
        success: false,
        uploadedCount: uploadedCount,
        skippedCount: skippedCount
      };
    } finally {
      sleepIfNeeded_(CONFIG.API_THROTTLE_MS);
    }
  }

  return {
    success: true,
    uploadedCount: uploadedCount,
    skippedCount: skippedCount
  };
}

function buildInvoiceDocumentFromZip_(attachmentName, zipBlob) {
  const pair = selectInvoiceFilesFromZip_(zipBlob);

  return {
    archive_name: attachmentName,
    archive_stem: sanitizeArchiveStem_(attachmentName),
    xml_file_name: baseName_(pair.xmlBlob.getName()),
    pdf_file_name: baseName_(pair.pdfBlob.getName()),
    xml_content_base64: Utilities.base64Encode(pair.xmlBlob.getBytes()),
    pdf_content_base64: Utilities.base64Encode(pair.pdfBlob.getBytes())
  };
}

function selectInvoiceFilesFromZip_(zipBlob) {
  const files = Utilities.unzip(zipBlob);
  const xmlFiles = [];
  const pdfFiles = [];

  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const name = baseName_(file.getName());

    if (/\.xml$/i.test(name)) {
      xmlFiles.push(file);
    } else if (/\.pdf$/i.test(name)) {
      pdfFiles.push(file);
    }
  }

  if (!xmlFiles.length) {
    throw new Error('ZIP does not contain any XML file.');
  }

  if (!pdfFiles.length) {
    throw new Error('ZIP does not contain any PDF file.');
  }

  if (xmlFiles.length === 1 && pdfFiles.length === 1) {
    return {
      xmlBlob: xmlFiles[0],
      pdfBlob: pdfFiles[0]
    };
  }

  const pdfByStem = {};
  for (let i = 0; i < pdfFiles.length; i++) {
    pdfByStem[fileStem_(baseName_(pdfFiles[i].getName()))] = pdfFiles[i];
  }

  for (let i = 0; i < xmlFiles.length; i++) {
    const xmlStem = fileStem_(baseName_(xmlFiles[i].getName()));
    if (pdfByStem[xmlStem]) {
      return {
        xmlBlob: xmlFiles[i],
        pdfBlob: pdfByStem[xmlStem]
      };
    }
  }

  throw new Error('ZIP must contain exactly one XML/PDF pair or matching XML/PDF file names.');
}

function uploadInvoiceDocument_(userEmail, invoiceDocument) {
  const url = CONFIG.API_BASE_URL.replace(/\/+$/, '') + '/invoices';
  const payload = {
    user_name: userEmail,
    documents: [invoiceDocument]
  };

  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'x-api-token': CONFIG.API_TOKEN
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  const httpStatusCode = response.getResponseCode();
  const rawText = response.getContentText() || '';
  let body = {};

  if (rawText) {
    try {
      body = JSON.parse(rawText);
    } catch (error) {
      body = {
        status: 'error',
        message: 'Non-JSON response: ' + truncateText_(rawText, 1000)
      };
    }
  }

  if (httpStatusCode < 200 || httpStatusCode >= 300) {
    throw new Error(
      'API request failed with HTTP ' +
      httpStatusCode +
      ': ' +
      truncateText_(body.message || rawText || 'Unknown error', 2000)
    );
  }

  if (body.status && body.status !== 'ok') {
    throw new Error(
      'API returned a non-ok payload: ' +
      truncateText_(body.message || JSON.stringify(body), 2000)
    );
  }

  return {
    httpStatusCode: httpStatusCode,
    body: body
  };
}

function sleepIfNeeded_(milliseconds) {
  const duration = Number(milliseconds) || 0;
  if (duration <= 0) {
    return;
  }
  Utilities.sleep(duration);
}

function loadSuccessfulAttachmentKeys_(logSheet) {
  const rows = getDataRows_(logSheet);
  const statusIndex = LOG_HEADERS.indexOf('status');
  const keyIndex = LOG_HEADERS.indexOf('attachment_key');
  const set = new Set();

  for (let i = 0; i < rows.length; i++) {
    if (String(rows[i][statusIndex]) === 'UPLOADED' && rows[i][keyIndex]) {
      set.add(String(rows[i][keyIndex]));
    }
  }

  return set;
}

function getStateMap_(stateSheet) {
  const rows = getDataRows_(stateSheet);
  const map = {};

  for (let i = 0; i < rows.length; i++) {
    const key = String(rows[i][0] || '').trim();
    if (!key) {
      continue;
    }
    map[key] = rows[i][1];
  }

  return map;
}

function setStateValues_(stateSheet, entries) {
  const nowIso = formatDateTimeBogota_(new Date());
  const existingRows = getDataRows_(stateSheet);
  const rowByKey = {};

  for (let i = 0; i < existingRows.length; i++) {
    const key = String(existingRows[i][0] || '').trim();
    if (key) {
      rowByKey[key] = i + 2;
    }
  }

  const keys = Object.keys(entries);
  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    const row = [key, entries[key], nowIso];

    if (rowByKey[key]) {
      stateSheet.getRange(rowByKey[key], 1, 1, 3).setValues([row]);
    } else {
      stateSheet.appendRow(row);
    }
  }
}

function appendLogRows_(logSheet, rows) {
  if (!rows || !rows.length) {
    return;
  }

  const startRow = logSheet.getLastRow() + 1;
  logSheet.getRange(startRow, 1, rows.length, rows[0].length).setValues(rows);
}

function getDataRows_(sheet) {
  const lastRow = sheet.getLastRow();
  const lastColumn = sheet.getLastColumn();

  if (lastRow <= 1 || lastColumn === 0) {
    return [];
  }

  return sheet.getRange(2, 1, lastRow - 1, lastColumn).getValues();
}

function isZipAttachment_(attachment) {
  const name = String(attachment.getName() || '').toLowerCase();
  const contentType = String(attachment.getContentType() || '').toLowerCase();

  return (
    /\.zip$/i.test(name) ||
    contentType === 'application/zip' ||
    contentType === 'application/x-zip-compressed'
  );
}

function extractEmailAddress_(rawFrom) {
  const normalized = String(rawFrom || '').trim().toLowerCase();
  const match = normalized.match(/[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}/i);
  return match ? match[0].toLowerCase() : normalized;
}

function sanitizeArchiveStem_(fileName) {
  const stem = fileStem_(baseName_(fileName))
    .replace(/[^\w.\-]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');

  return stem || 'invoice';
}

function baseName_(path) {
  return String(path || '').split('/').pop().split('\\').pop();
}

function fileStem_(fileName) {
  return String(fileName || '').replace(/\.[^.]+$/, '');
}

function sha256Hex_(bytes) {
  const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes);
  let hex = '';

  for (let i = 0; i < digest.length; i++) {
    let value = digest[i];
    if (value < 0) {
      value += 256;
    }
    const fragment = value.toString(16);
    hex += fragment.length === 1 ? '0' + fragment : fragment;
  }

  return hex;
}

function formatDateForGmailQuery_(date) {
  return Utilities.formatDate(date, CONFIG.BOGOTA_TIMEZONE, 'yyyy/MM/dd');
}

function formatDateTimeBogota_(date) {
  return Utilities.formatDate(date, CONFIG.BOGOTA_TIMEZONE, "yyyy-MM-dd'T'HH:mm:ss'-05:00'");
}

function normalizeCellText_(value) {
  return String(value || '').replace(/\s+/g, ' ').trim();
}

function truncateText_(value, maxLength) {
  const text = String(value || '');
  if (text.length <= maxLength) {
    return text;
  }
  return text.slice(0, maxLength - 3) + '...';
}

function getNestedValue_(obj, path) {
  let current = obj;
  for (let i = 0; i < path.length; i++) {
    if (current === null || current === undefined) {
      return '';
    }
    current = current[path[i]];
  }
  return current === undefined || current === null ? '' : current;
}
