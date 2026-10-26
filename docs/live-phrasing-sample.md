# Live phrasing sample

Model sentences from the verified deployment (`gpt-4.1-mini`, Global Standard, France Central; prompt `p4`) for showcase claims, beside the template sentence the committed UI shows. Every model sentence passed the output guard (`agents/output_guard.py`). That means the same numbers as the claim, no other number, no other team or player, no banned or prediction wording, and the right language. The sentences live in `data/phrasing-cache/` and are used only on the Azure phraser path (`python -m agents.run_match --phraser azure`); `web/public/data` stays template-based.

Run: 49 claims, 49 calls, 120 of 147 sentences accepted, 27 rejected (template kept), 29836 prompt and 4955 completion tokens.

## `attack_side.stat`

| | Template | Model (accepted) |
|---|---|---|
| en | NTG attack mostly down the right side: 60.9% of their entries into the final third. | NTG attacked down the right side 60.9% of the time while trailing by multiple goals in the first part of the match. |
| es | NTG ataca sobre todo por el costado derecho: el 60,9% de sus entradas al último tercio. | NTG atacó por el lado derecho el 60,9% del tiempo mientras perdía por varios goles en la primera parte del partido. |
| fr | NTG attaque surtout par le côté droit : 60,9 % de ses entrées dans le dernier tiers. | NTG a attaqué sur le côté droit 60,9% du temps en étant mené de plusieurs buts dans la première partie du match. |

## `chances_created.stat`

| | Template | Model (accepted) |
|---|---|---|
| en | Bodhi Quinfen has set up 3 chances for AUR. | Bodhi Quinfen from AUR created 3 chances in open play while leading comfortably. |
| es | Bodhi Quinfen ha dado 3 ocasiones a AUR. | Bodhi Quinfen de AUR creó 3 ocasiones en juego abierto mientras lideraba con comodidad. |
| fr | Bodhi Quinfen a offert 3 occasions à AUR. | Bodhi Quinfen d'AUR a créé 3 occasions en jeu ouvert en menant largement. |

## `chances_created.split`

| | Template | Model (accepted) |
|---|---|---|
| en | Callum Corzek has set up 8 chances, but 7 came from set pieces and only 1 in open play. | Callum Corzek created 8 chances for NTG, including 1 from open play and 7 from set pieces while trailing by multiple goals. |
| es | Callum Corzek ha dado 8 ocasiones, pero 7 llegaron a balón parado y solo 1 en juego abierto. | Callum Corzek creó 8 ocasiones para NTG, incluyendo 1 en juego abierto y 7 en jugadas a balón parado mientras iban perdiendo por varios goles. |
| fr | Callum Corzek a offert 8 occasions, mais 7 sont venues de coups de pied arrêtés et seulement 1 dans le jeu. | Callum Corzek a créé 8 occasions pour NTG, dont 1 en jeu ouvert et 7 sur coups de pied arrêtés alors que l'équipe était menée de plusieurs buts. |

## `crosses.stat`

| | Template | Model (accepted) |
|---|---|---|
| en | NTG put 18 crosses into the box. | NTG completed 18 crosses while trailing by multiple goals. |
| es | NTG puso 18 centros al área. | NTG completó 18 centros mientras iba perdiendo por varios goles. |
| fr | NTG a envoyé 18 centres dans la surface. | NTG a réalisé 18 centres en étant mené de plusieurs buts. |

## `field_tilt.stat`

| | Template | Model (accepted) |
|---|---|---|
| en | AUR are camped in the opposition half: 70.6% of the final-third passing is theirs. | AUR controlled 70.6% of the field tilt in the first part of the match while the score was level. |
| es | AUR está instalado en campo rival: suyo es el 70,6 % del juego en el último tercio. | AUR dominó el 70,6% de la inclinación del campo en la primera parte del partido con el marcador igualado. |
| fr | AUR campe dans le camp adverse : 70,6 % des passes dans le dernier tiers sont les siennes. | AUR a contrôlé 70,6 % de l'inclinaison du terrain dans la première partie du match alors que le score était à égalité. |

## `f3_losses.stat`

| | Template | Model (accepted) |
|---|---|---|
| en | AUR gave the ball away 25 times in the final third. | AUR lost the ball 25 times in the final third while leading comfortably. |
| es | AUR regaló el balón 25 veces en el último tercio. | AUR perdió el balón 25 veces en el último tercio mientras iba ganando cómodamente. |
| fr | AUR a rendu le ballon 25 fois dans le dernier tiers. | AUR a perdu le ballon 25 fois dans le dernier tiers du terrain en menant largement. |

## Rejected by the guard (template kept)

Claim `pattern.direct_transition`, en: "AUR completed 4 direct transitions with 26 regains and an xG of 0.5 while leading comfortably against NTG, exceeding the league rate of 2.6 per 100."

Reason: numbers: param per_100=15.4 missing. The model left out the claim's own rate (15.4 per 100), so the sentence never reached the stream and the template sentence was used.
