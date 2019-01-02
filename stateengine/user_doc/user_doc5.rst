.. index:: Plugins; Stateengine; Ausführungszeitpunkt
.. index:: Ausführungszeitpunkt

Ausführungszeitpunkt
####################

Um festzulegen, wann die Aktionen eines Zustands ausgeführt
werden, gibt es vier Ereignisse, denen die Aktionen zugeordnet
werden können: Für jedes dieser Ereignisse wird ein Item unterhalb
des Zustands-Items angelegt, unterhalb dem die jeweiligen Aktionen
als Attribute definiert werden.

-  **on_enter**: Aktionen, die nur beim erstmaligen Aktivieren des
   Zustands ausgeführt werden

-  **on_stay**: Aktionen, die nur ausgeführt werden, wenn der Zustand
   zuvor bereits aktiv war und weiterhin aktiv bleibt.

-  **on_enter_or_stay**: Aktionen, die ausgeführt werden, wenn der
   Zustand aktiv ist, unabhängig davon, ob er bereits zuvor aktiv
   war oder nicht.

-  **on_leave**: Aktionen, die ausgeführt werden, direkt bevor ein
   anderer Zustand aktiv wird.

**Beispiel**

.. code-block:: yaml

  test:
      events:
          name: stateengine Event Beispiel
          type: foo

          rules:
              type: bool
              name: Automatik Test Event
              # Dies ist ein Objekt-Item für das stateengine-Plugin:
              se_plugin: active

              state1:
                  type: foo
                  name: Status 1

                  on_enter:
                     name: Ausführen immer wenn ein Zustand gerade aktiv geworden ist
                     <... Aktionen ...>

                  on_stay:
                     name: Ausführen immer wenn ein Zustand aktiv geworden ist und bereits vorher aktiv war
                     <... Aktionen ...>

                  on_enter_or_stay:
                     name: Ausführen immer wenn ein Zustand aktiv ist
                     <... Aktionen ...>

                  on_leave:
                     name: Ausführen beim Verlassen des Zustands
                     <... Aktionen ...>

                  enter_1:
                     name: Bedingung 1
                     <...Einstiegs-Bedingungsset 1...>

                  enter_2:
                     name: Bedingung 2
                     <...Einstiegs-Bedingungsset 2...>

              state2:
                  name: Status 2
                  <... Weitere Bedingungssets und Aktionsgruppen ...>
