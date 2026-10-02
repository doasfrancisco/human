# Feedback from Matías, 2026-10-01

## First use

1. **The skill starts the user.** The skill makes the first global flow, opens the reader link, show something that lets the user know it can edit the human code, If the user tries to continue to program by chat and not through human, the skill refuses.

   The first flow is very short and compact, one numbered line per step, with pins. Example, from Matías's project `ol.human`:


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

2. **No `human init`.** human is only a web page. When a new version is available, an "update web" button shows.

## Reader

working 3. **Code highlights.** Show the code with colours (syntax highlighting).
working 4. **Open the abstraction by default.**

working 6. **Remove the grey text above the abstractions.**
working 7. **Add tab.**
working 8. **Go back after a pin jump.** After a click on a pin, Alt+Left or the browser back button returns to the start position.
working 9. **The bottom of the reader is too high.** On Matías's screen the edit box stops at about two thirds of the window height. When he edits, the text is cut through the middle of a line (line 5 above), and the space below the box stays empty.

## Buttons

working 10. **Save button.** Change the check icon to a "save" button, in yellow.
working 11. **Run button.** Make "run" colourful and green. 

12. instal by curl like curl -fsSL https://claude.ai/install.sh | bash

## Skills

working 12. **Delete the decompile skill**, if human does all of its work.

## Fixed

13. **Pins did not jump on Matías's computer.** Fixed in 0.0.92: a pin to a real file now jumps, also when that file has no map.
