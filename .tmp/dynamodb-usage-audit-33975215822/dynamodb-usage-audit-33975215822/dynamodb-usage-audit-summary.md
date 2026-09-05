## DynamoDB usage audit

- Window UTC: `2026-09-01T15:34:39.568871+00:00` -> `2026-09-05T15:34:39.568871+00:00`
- Lookback days: `4`
- Table prefix: `trii-prod-`
- Tables analyzed: `7`
- Approx total write units: `6353958.00`
- Approx total read units: `3181857.00`

### Top tables by writes

| Table | Approx writes | Approx reads | Write/Read ratio | Indexes |
| --- | ---: | ---: | ---: | ---: |
| trii-prod-historic-stats | 5419054.00 | 1598808.50 | 3.39 | 1 |
| trii-prod-current-snapshots | 456661.00 | 1173943.00 | 0.39 | 1 |
| trii-prod-analytics-catalog | 260552.00 | 39709.00 | 6.56 | 0 |
| trii-prod-session-vectors | 217408.00 | 254108.00 | 0.86 | 0 |
| trii-prod-daily-closing-snapshots | 180.00 | 12122.00 | 0.01 | 1 |
| trii-prod-stock-orders | 103.00 | 103166.50 | 0.00 | 2 |
| trii-prod-parsed-invoices | 0.00 | 0.00 | n/a | 2 |

### Cost Explorer by usage type

| Usage type | Cost USD | Usage quantity |
| --- | ---: | ---: |
| WriteRequestUnits | 4.9249 | 7879833.00 |
| ReadRequestUnits | 0.4937 | 3949752.50 |
| USE1-TimedPITRStorage-ByteHrs | 0.0021 | 0.01 |
| TimedStorage-ByteHrs | 0.0000 | 0.02 |
| USE1-Streams-Requests | 0.0000 | 1.00 |
