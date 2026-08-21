# Terraform en AWS

Esta base de infraestructura deja un flujo ordenado para `trii` con GitHub Actions, OIDC y un backend remoto en S3.

## Decision de arquitectura

El bucket del backend tiene un problema de arranque: no puede guardar su propio estado remoto antes de existir.

Por eso separamos la infraestructura en dos capas:

- `infra/scripts/bootstrap-state-bucket.sh`: asegura el bucket del backend de forma idempotente antes de `terraform init`.
- `infra/bootstrap`: deja un root module aislado por si mas adelante quieres reconciliar ese bucket desde Terraform en un flujo manual.
- `infra/prod`: usa el bucket anterior como backend remoto en S3. Aqui viviran los servicios reales del ambiente.

Esto mantiene el flujo simple y evita scripts manuales fuera de Terraform.

## Valores iniciales

- AWS account: `311923415472`
- Region: `us-east-1`
- Repo: `danielnmuner/trii`
- Role ARN: `arn:aws:iam::311923415472:role/GitHubTerraformTriiRole`
- Bucket de state: `trii-terraform-state-311923415472-us-east-1`
- Key del state remoto: `prod/terraform.tfstate`

## Estructura

- `infra/modules/terraform-state-bucket`: modulo reutilizable para el bucket del backend.
- `infra/scripts/bootstrap-state-bucket.sh`: script idempotente para asegurar el bucket del backend.
- `infra/bootstrap`: root module opcional para trabajo manual sobre el bucket del backend.
- `infra/prod`: root module del ambiente productivo, ya configurado para usar backend remoto en S3.
- `.github/workflows/terraform-plan-apply.yml`: valida, hace plan y aplica.
- `.github/workflows/terraform-destroy.yml`: destruye recursos del root `prod`, pero no el bucket del backend.
- `.github/workflows/historic-stats-backfill.yml`: invoca manualmente la Lambda `trii-prod-historic-stats-backfill` con inputs operativos.

## Flujo esperado

### 1. Apply

El workflow hace:

1. Checkout del repo.
2. Asume el rol `GitHubTerraformTriiRole` por OIDC.
3. Ejecuta `infra/scripts/bootstrap-state-bucket.sh` para asegurar el bucket del backend.
4. Ejecuta `infra/prod` con backend remoto en S3.
5. Corre `init`, `validate`, `plan` y `apply`.

### 2. Destroy

El workflow:

1. Requiere confirmacion manual.
2. Reasegura el bucket del backend con `infra/scripts/bootstrap-state-bucket.sh`.
3. Ejecuta `terraform destroy` solo sobre `infra/prod`.

El bucket del backend queda protegido con `prevent_destroy`.

### 3. Historic stats backfill

El workflow manual de backfill:

1. Hace checkout del repo.
2. Asume el rol `GitHubTerraformTriiRole` por OIDC.
3. Construye un payload JSON para `trii-prod-historic-stats-backfill`.
4. Invoca la Lambda de backfill de forma sincronica.
5. Publica el payload y la respuesta como resumen y artefactos del run.

Este flujo esta pensado para reconstruir una metrica puntual ya soportada por la Lambda, normalmente primero en `preview` y luego en `apply`.

## Nota sobre el role OIDC

El workflow asume que el trust policy del rol permite este repositorio en GitHub Actions.

Si hoy el rol solo permite otro repo, habra que ampliar el `sub` correspondiente para `danielnmuner/trii`.

Ademas del trust policy, ese rol debe tener permisos suficientes para:

- operar Terraform sobre los recursos del ambiente `prod`
- invocar `trii-prod-historic-stats-backfill` cuando se use el workflow manual de backfill
