# Azure live check

Run 2026-10-26T09:32:48+00:00: deployment `optix-phraser`, auth entra-id, 3 model calls (cap 10).

- sentences accepted by the output guard: 6; rejected (template used): 3
- phraser.call spans captured: 3
- number guard passed on every sentence: True

| claim | language | source | guard | casual sentence |
|---|---|---|---|---|
| `field_tilt.low_block_and_counters` | en | model | accepted | NTG had 80% field tilt with 7 shots and 0.043 xG per shot, conceding 4 counter shots with 0.53 counter xG and 71.4% outside shot share while trailing by 4 goals. |
| `field_tilt.low_block_and_counters` | es | model | accepted | NTG tuvo un 80% de dominio del campo con 7 tiros y 0,043 xG por tiro, concediendo 4 tiros de contraataque con 0,53 xG en contra y 71,4% de tiros desde fuera mientras perdía por 4 goles. |
| `field_tilt.low_block_and_counters` | fr | model | accepted | NTG a eu 80% d'inclinaison de terrain avec 7 tirs et 0,043 xG par tir, concédant 4 tirs en contre avec 0,53 xG contre et 71,4% de tirs extérieurs tout en étant mené de 4 buts. |
| `xg.volume_and_set_pieces` | en | model | accepted | NTG had an xG of 1.03 from 20 shots, with 0.59 xG from set pieces making up 57.7% of their total xG and an xG per shot of 0.051. |
| `xg.volume_and_set_pieces` | es | model | accepted | NTG tuvo un xG de 1,03 en 20 tiros, con 0,59 xG de jugadas a balón parado que representaron el 57,7% de su xG total y un xG por tiro de 0,051. |
| `xg.volume_and_set_pieces` | fr | model | accepted | NTG a eu un xG de 1,03 sur 20 tirs, avec 0,59 xG provenant des coups de pied arrêtés représentant 57,7 % de leur xG total et un xG par tir de 0,051. |
| `pattern.direct_transition` | en | template | numbers: param per_100=15.4 missing; numbers: number 100 is not a param | From their own half to a shot in seconds: 4 times in 26 regains for AUR, 0.5 xG, 15.4 per hundred (league 2.6). |
| `pattern.direct_transition` | es | template | numbers: param per_100=15,4 missing; numbers: number 100 is not a param | De campo propio al tiro en segundos: 4 veces en 26 recuperaciones para AUR, 0,5 xG, 15,4 por cada cien (liga 2,6). |
| `pattern.direct_transition` | fr | template | numbers: param per_100=15,4 missing; numbers: number 100 is not a param | De son camp au tir en quelques secondes : 4 fois sur 26 récupérations pour AUR, 0,5 xG, 15,4 toutes les cent (ligue 2,6). |

## How to run it

1. `az login` (Microsoft Entra ID; the phraser uses DefaultAzureCredential, no key needed).
2. Give your user the **Cognitive Services OpenAI User** role on the Azure OpenAI / Foundry resource.
3. Copy `.env.example` to `.env` and set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT`
   (optional: `AZURE_OPENAI_API_VERSION`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).
4. `pip install -r requirements-azure.txt`
5. `python -m tools.azure_live_check` (at most 10 model calls), then
   `python -m pytest -m azure_live` for the live tests.
