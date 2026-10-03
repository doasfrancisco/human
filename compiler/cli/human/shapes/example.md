# example

The first global flow of a project that already has code. Claude writes it on the first use, in the project map, so the user reads the whole project in one look and sees where to change it.

Validated on: Matías's project `ol.human`.

## Rules

- Very short and compact: one numbered line per step of the main run, in the order things happen.
- A step names the part that acts and pins it: `[Resolutor](orquestador/src/orq/resolver.py:process)`.
- A step may hold two or three short lines under it, indented, for the branches: `- when this → [that step](file:block)`.
- Say when a step runs, if it runs on a clock: `(every 2 min)`.
- Pins go on the words that name the thing, never on a whole line.
- No telling of how a part works inside: that is the work of the file's own abstraction.
- Write in the language the user writes in.

## Example

```
1. Ingesta (cada 2 min): [orq-poll-requests](orquestador/src/orq/handlers/poll_requests.py:handler) [toma las solicitudes en 1 · Registrada](…)
  2. [Resolutor](orquestador/src/orq/resolver.py:process): comprueba plataforma, flujo encendido y [estudio permitido](…)
     [arma el payload](orquestador/src/orq/automation/mapper.py:build).
     - Falta un dato del estudio (fecha o foto) → [4 · Solicitud de cambios](orquestador/src/orq/resolver.py:_cambios).
     - Falta un dato que depende de TWL (correo, foto con 404) → [3 · Detenida](orquestador/src/orq/resolver.py:_stop).
  3. [Máquina org-account-creation](orquestador/src/orq/handlers/account_step.py:handler):
     - [Submit/Poll](orquestador/src/orq/executor.py:submit): crea la cuenta en la plataforma con la [API de automatizaciones](…)
     - [Publish](orquestador/src/orq/executor.py:publish): llama a [approveCatafractStudioRequest](orquestador/src/orq/twl/requests.py:approve), …
     - [Close](orquestador/src/orq/executor.py:close): comprueba que quedó en 5 y marca el ítem done.
  4. [Si falla](orquestador/src/orq/executor.py:fail): primero relee. Si el error es del estudio ([nick tomado, datos rechazados](…) …
  5. [Vuelta desde 4](orquestador/src/orq/handlers/retake_changes.py:handler) (cada 15 min): si el estudio corrigió el dato, [la solicitud …](…)
```
