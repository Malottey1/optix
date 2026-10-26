# Azure live check

Run 2026-10-26T09:40:56+00:00: deployment `optix-phraser`, auth entra-id, 3 model calls (cap 10).

- sentences accepted by the output guard: 0; rejected (template used): 9
- phraser.call spans captured in memory: 3
- application insights export: not attempted (APPLICATIONINSIGHTS_CONNECTION_STRING not set)
- number guard passed on every sentence: True

| claim | language | source | guard | casual sentence |
|---|---|---|---|---|
| `field_tilt.low_block_and_counters` | en | template | numbers: number 2 is not a param | NTG had 80% of the territory, yet 71.4% of their 7 shots were from distance (0.043 xG a shot) and 4 shots on the break went the other way (0.53 xG). |
| `field_tilt.low_block_and_counters` | es | template | numbers: number 2 is not a param | NTG tuvo el 80% del territorio, pero el 71,4% de sus 7 tiros fue de lejos (0,043 xG por tiro) y recibió 4 tiros a la contra (0,53 xG). |
| `field_tilt.low_block_and_counters` | fr | template | numbers: number 100 is not a param; numbers: number 100 is not a param; numbers: number 2 is not a param | NTG avait 80 % du territoire, mais 71,4 % de ses 7 tirs venaient de loin (0,043 xG par tir) et a encaissé 4 tirs en contre (0,53 xG). |
| `xg.volume_and_set_pieces` | en | template | numbers: number 100 is not a param | NTG have taken 20 shots worth 1.03 expected goals (0.051 a shot), and 0.59 of it came from set pieces (57.7% without penalties). |
| `xg.volume_and_set_pieces` | es | template | numbers: number 100 is not a param | NTG lleva 20 tiros que valen 1,03 goles esperados (0,051 por tiro), y 0,59 llegaron a balón parado (57,7% sin penaltis). |
| `xg.volume_and_set_pieces` | fr | template | numbers: number 100 is not a param | NTG a tiré 20 fois pour 1,03 buts attendus (0,051 par tir), dont 0,59 sur coups de pied arrêtés (57,7 % hors penalty). |
| `pattern.direct_transition` | en | template | numbers: number 2 is not a param | From their own half to a shot in seconds: 4 times in 26 regains for AUR, 0.5 xG, 15.4 per hundred (league 2.6). |
| `pattern.direct_transition` | es | template | numbers: number 2 is not a param | De campo propio al tiro en segundos: 4 veces en 26 recuperaciones para AUR, 0,5 xG, 15,4 por cada cien (liga 2,6). |
| `pattern.direct_transition` | fr | template | numbers: number 2 is not a param | De son camp au tir en quelques secondes : 4 fois sur 26 récupérations pour AUR, 0,5 xG, 15,4 toutes les cent (ligue 2,6). |

## How to run it

1. `az login` (Microsoft Entra ID; the phraser uses DefaultAzureCredential, no key needed).
2. Give your user the **Cognitive Services OpenAI User** role on the Azure OpenAI / Foundry resource.
3. Copy `.env.example` to `.env` and set `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_DEPLOYMENT`
   (optional: `AZURE_OPENAI_API_VERSION`, `APPLICATIONINSIGHTS_CONNECTION_STRING`).
4. `pip install -r requirements-azure.txt`
5. `python -m tools.azure_live_check` (at most 10 model calls), then
   `python -m pytest -m azure_live` for the live tests.
