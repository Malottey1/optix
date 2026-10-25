# es / fr strings for native-speaker review

Every interface string added or changed in the final UI run (web/src/lib/i18n-final.ts, plus the
changed keys in web/src/lib/i18n.ts listed at the end). The English is the source; the Spanish and
French were written without a native speaker and need a review. Rules for any fix: no digits in a
string (numbers are filled in at runtime from `{placeholders}`), observational wording only (the
banned-word lists in tools/ apply), keep every `{placeholder}`.

192 keys.

| Key | English | Español | Français |
|---|---|---|---|
| `tech_details` | Technical details | Detalles técnicos | Détails techniques |
| `tech_details_sub` | Rules, contracts, limits | Reglas, contratos, límites | Règles, contrats, limites |
| `kits_note` | Kits and club artwork are illustrative, for fictional clubs. | Las equipaciones y los escudos son ilustraciones de clubes ficticios. | Les maillots et les écussons sont des illustrations de clubs fictifs. |
| `hub_lineups` | Lineups | Alineaciones | Compositions |
| `panel_title` | Insights and patterns | Datos y patrones | Analyses et motifs |
| `panel_insights` | Insights | Datos | Analyses |
| `panel_patterns` | Patterns | Patrones | Motifs |
| `panel_family` | Pattern family | Familia de patrón | Famille de motif |
| `panel_all` | All | Todos | Tous |
| `panel_pages` | Pages | Páginas | Pages |
| `panel_prev` | Previous | Anterior | Précédent |
| `panel_next` | Next | Siguiente | Suivant |
| `panel_page` | Page {k} of {n} | Página {k} de {n} | Page {k} sur {n} |
| `panel_per_page` | Cards per page | Tarjetas por página | Cartes par page |
| `lu_xi` | Starting XI | Once inicial | Onze de départ |
| `lu_off` | Off | Sale | Sort |
| `lu_on` | On | Entra | Entre |
| `lu_note` | Starting XIs by listed position. Not a tracked shape. | Onces iniciales por posición listada. No es una forma medida. | Onze de départ par poste listé. Pas une forme mesurée. |
| `mu_attacking` | {team} attacking | {team} en ataque | {team} en attaque |
| `mu_defending` | {team} defending | {team} en defensa | {team} en défense |
| `mu_sub` | Season figures. | Cifras de la temporada. | Chiffres de la saison. |
| `mu_att_label` | Entry share | Cuota de entradas | Part des entrées |
| `mu_def_label` | Completion conceded | Acierto concedido | Réussite concédée |
| `mu_delta` | Δ vs league, pts | Δ frente a la liga, pts | Δ face à la ligue, pts |
| `mu_sentence` | {a}: {as}% of final-third entries down the {lane} (league {ls}%). Opponents completed {cc}% of entry passes there against {d} (league {lc}%). | {a}: {as}% de sus entradas al último tercio por el {lane} (liga {ls}%). Los rivales completaron allí el {cc}% de los pases de entrada contra {d} (liga {lc}%). | {a} : {as} % de ses entrées dans le dernier tiers par le {lane} (ligue {ls} %). Les adversaires y ont réussi {cc} % des passes d'entrée contre {d} (ligue {lc} %). |
| `mu_tbl_share` | {team} share % | {team} porcentaje | {team} part en % |
| `mu_tbl_comp` | {team} conceded completion % | {team} acierto concedido | {team} réussite concédée en % |
| `mu_rule_note` | Shown when the Verifier passed the lane claim at medium or high confidence. Season figures, all matches. | Se muestra cuando el Verificador aprobó la afirmación del carril con confianza media o alta. Cifras de la temporada. | Affiché quand le Vérificateur a validé l'affirmation de couloir avec une confiance moyenne ou élevée. Chiffres de la saison. |
| `st_tempo` | Tempo | Ritmo | Tempo |
| `st_tempo_unit` | seconds between passes | segundos entre pases | secondes entre les passes |
| `st_press` | Press | Presión | Pressing |
| `st_passing` | Passing | Pase | Passes |
| `st_territory` | Territory | Territorio | Territoire |
| `st_counters` | Counters | Contras | Contres |
| `st_league` | League | Liga | Ligue |
| `st_vs` | against the league average | frente a la media de la liga | face à la moyenne de la ligue |
| `st_caption` | Bars run from the lowest to the highest team in the league. | Las barras van del equipo más bajo al más alto de la liga. | Les barres vont de l'équipe la plus basse à la plus haute de la ligue. |
| `st_chip_highest` | Highest of {n} | El más alto de {n} | Le plus haut des {n} |
| `st_chip_lowest` | Lowest of {n} | El más bajo de {n} | Le plus bas des {n} |
| `st_chip_above` | Above average | Sobre la media | Au-dessus |
| `st_chip_below` | Below average | Bajo la media | En dessous |
| `st_chip_average` | About average | En la media | Dans la moyenne |
| `st_lowest` | Lowest team | Equipo más bajo | Équipe la plus basse |
| `st_highest` | Highest team | Equipo más alto | Équipe la plus haute |
| `pp_minutes` | Minutes | Minutos | Minutes |
| `pp_starts` | Starts | Titularidades | Titularisations |
| `pp_bench` | Off the bench | Desde el banquillo | En sortie de banc |
| `pp_na` | Not available in event data | No disponible en los datos de eventos | Indisponible dans les données d'événements |
| `pp_na_link` | See the limits | Ver los límites | Voir les limites |
| `pp_na_ground` | Ground duels | Duelos en el suelo | Duels au sol |
| `pp_na_regain` | Pressure regains | Recuperaciones tras presión | Récupérations après pressing |
| `pp_na_save` | Save location and post-shot quality | Lugar de la parada y calidad tras el tiro | Lieu de l'arrêt et qualité après le tir |
| `pp_na_lines` | Line-breaking passes and off-ball runs | Pases que rompen líneas y desmarques sin balón | Passes qui cassent les lignes et appels sans ballon |
| `pp_routes_note` | Each line is one completed pass. Showing the {n} most progressive. | Cada línea es un pase completado. Se muestran los {n} más progresivos. | Chaque ligne est une passe réussie. Les {n} plus progressives sont affichées. |
| `pp_peers` | Peers: same listed position ({pos}), at least {n} minutes | Pares: misma posición ({pos}), al menos {n} minutos | Pairs : même poste ({pos}), au moins {n} minutes |
| `def_title` | Defensive actions | Acciones defensivas | Actions défensives |
| `def_total` | Season total | Total de temporada | Total de la saison |
| `def_p90` | Per ninety | Por noventa | Par quatre-vingt-dix |
| `def_p100` | Per hundred opposition entries | Por cien entradas rivales | Pour cent entrées adverses |
| `def_pctl` | Percentile among peers | Percentil entre sus pares | Centile parmi les pairs |
| `def_peer_avg` | Peer average | Media de sus pares | Moyenne des pairs |
| `def_tackles` | Tackles | Entradas | Tacles |
| `def_interceptions` | Interceptions | Intercepciones | Interceptions |
| `def_blocks` | Blocks | Bloqueos | Contres |
| `def_clearances` | Clearances | Despejes | Dégagements |
| `def_fouls` | Fouls | Faltas | Fautes |
| `def_contributions` | Defensive contributions | Contribuciones defensivas | Contributions défensives |
| `def_contrib_def` | Defensive contributions: tackles, interceptions, blocks and clearances added together. | Contribuciones defensivas: entradas, intercepciones, bloqueos y despejes sumados. | Contributions défensives : tacles, interceptions, contres et dégagements additionnés. |
| `def_floor` | Rates appear from {n} minutes played. | Las tasas aparecen a partir de {n} minutos jugados. | Les taux apparaissent à partir de {n} minutes jouées. |
| `def_bars_note` | Bars run left or right of the peer median. | Las barras salen a izquierda o derecha de la mediana de sus pares. | Les barres partent à gauche ou à droite de la médiane des pairs. |
| `def_map` | Defensive action map | Mapa de acciones defensivas | Carte des actions défensives |
| `def_map_note` | Where each action took place, own goal on the left. Event locations, not tracking. | Dónde ocurrió cada acción, portería propia a la izquierda. Lugares de eventos, no seguimiento. | Où chaque action a eu lieu, propre but à gauche. Lieux d'événements, pas de suivi. |
| `def_map_types` | Action types | Tipos de acción | Types d'action |
| `pass_title` | Progressive passing | Pase progresivo | Passes progressives |
| `pass_prog` | Progressive passes | Pases progresivos | Passes progressives |
| `pass_f3` | Into the final third | Al último tercio | Vers le dernier tiers |
| `pass_box` | Into the box | Al área | Dans la surface |
| `gk_map` | Shots faced | Tiros recibidos | Tirs subis |
| `gk_map_note` | Where each shot was taken, own goal on the left. | Desde dónde se lanzó cada tiro, portería propia a la izquierda. | D'où chaque tir a été pris, propre but à gauche. |
| `gk_figures` | Shot stopping | Paradas | Arrêts |
| `gk_saves` | Saves | Paradas | Arrêts |
| `gk_on_target` | On target | A puerta | Cadrés |
| `gk_save_pct` | Save rate | Porcentaje de paradas | Taux d'arrêts |
| `gk_conceded` | Goals conceded | Goles encajados | Buts encaissés |
| `gk_xg_faced` | xG faced | xG recibido | xG subis |
| `gk_diff` | Conceded minus xG faced | Encajados menos xG recibido | Encaissés moins xG subis |
| `gk_clean` | Clean sheets | Porterías a cero | Clean sheets |
| `gk_dist` | Distribution | Distribución | Relance |
| `gk_passes` | Passes | Pases | Passes |
| `gk_completion` | Completion | Acierto | Réussite |
| `gk_long` | Long passes | Pases largos | Passes longues |
| `gk_long_def` | Long: at least {m} m. | Largo: al menos {m} m. | Longue : au moins {m} m. |
| `gk_goal_kicks` | Goal kicks | Saques de puerta | Six mètres |
| `res_goal` | Goal | Gol | But |
| `res_saved` | Saved | Parado | Arrêté |
| `res_blocked` | Blocked | Bloqueado | Contré |
| `res_off_target` | Off target | Fuera | Non cadré |
| `ch_title` | Chances created | Ocasiones creadas | Occasions créées |
| `ch_open` | Open the evidence | Abrir las pruebas | Ouvrir les preuves |
| `ch_total` | Total chances | Ocasiones en total | Occasions au total |
| `ch_sp` | From set pieces | A balón parado | Sur coups de pied arrêtés |
| `ch_op` | From open play | En juego abierto | Dans le jeu |
| `ch_xa_per` | xA per chance | xA por ocasión | xA par occasion |
| `ch_league` | League {v} | Liga {v} | Ligue {v} |
| `ch_all` | All | Todas | Toutes |
| `ch_kind_corner` | Corners | Córneres | Corners |
| `ch_kind_free_kick` | Free kicks | Faltas | Coups francs |
| `ch_kind_throw_in` | Throw-ins | Saques de banda | Touches |
| `ch_kind_set_piece` | Other set pieces | Otras jugadas a balón parado | Autres coups de pied arrêtés |
| `ch_kind_open_play` | Open play | Juego abierto | Jeu |
| `ch_key` | Key passes | Pases clave | Passes clés |
| `ch_prog` | Progressive | Progresivos | Progressives |
| `ch_fwd` | Forward | Hacia delante | Vers l'avant |
| `ch_breakdown` | Breakdown | Desglose | Détail |
| `ch_list` | Every chance | Cada ocasión | Chaque occasion |
| `ch_minute` | Minute | Minuto | Minute |
| `ch_type` | Type | Tipo | Type |
| `ch_pass` | Pass | Pase | Passe |
| `ch_result` | Shot | Tiro | Tir |
| `ch_play` | Play | Ver | Voir |
| `ch_play_label` | Open the match at {t} | Abrir el partido en {t} | Ouvrir le match à {t} |
| `ch_sentence` | {name} created {n} chances: {sp} from set pieces and {op} from open play. | {name} creó {n} ocasiones: {sp} a balón parado y {op} en juego abierto. | {name} a créé {n} occasions : {sp} sur coups de pied arrêtés et {op} dans le jeu. |
| `ch_what` | What this shows: each line runs from where the pass started to where it ended, next to the shot it set up. | Qué muestra: cada línea va de donde empezó el pase a donde terminó, junto al tiro que preparó. | Ce que cela montre : chaque ligne va du départ de la passe à son arrivée, près du tir qu'elle a préparé. |
| `ch_legend_line` | Pass | Pase | Passe |
| `ch_legend_shot` | Resulting shot | Tiro resultante | Tir qui suit |
| `ch_none` | No chances created in the season. | Ninguna ocasión creada en la temporada. | Aucune occasion créée sur la saison. |
| `pt_short` | Short | Corto | Courte |
| `pt_long_ball` | Long ball | Balón largo | Ballon long |
| `pt_through_ball` | Through ball | Pase al hueco | Passe en profondeur |
| `pt_cross` | Cross | Centro | Centre |
| `pt_corner` | Corner | Córner | Corner |
| `pt_free_kick` | Free kick | Falta | Coup franc |
| `pt_throw_in` | Throw-in | Saque de banda | Touche |
| `ho_showcase` | Showcase match | Partido escaparate | Match vitrine |
| `ho_live_chip` | Live replay | Repetición en directo | Rediffusion en direct |
| `ho_final_chip` | Final | Final | Terminé |
| `ho_explore` | Explore Match Hub | Explorar el centro del partido | Explorer le centre du match |
| `ho_timeline` | Goals, cards and substitutions | Goles, tarjetas y cambios | Buts, cartons et remplacements |
| `ho_insights` | Key insights | Claves del partido | Points clés |
| `ho_view_all` | View all insights | Ver todas las claves | Voir tous les points clés |
| `ho_evidence` | Evidence | Pruebas | Preuves |
| `ho_xg` | xG race | Carrera de xG | Course aux xG |
| `ho_xg_note` | Cumulative expected goals over the match. | Goles esperados acumulados durante el partido. | Buts attendus cumulés sur le match. |
| `ho_momentum` | Momentum | Impulso | Dynamique |
| `ho_momentum_note` | Above the line: {home}. Below: {away}. | Encima de la línea: {home}. Debajo: {away}. | Au-dessus de la ligne : {home}. En dessous : {away}. |
| `ho_heat` | Where the ball was | Dónde estuvo el balón | Où était le ballon |
| `ho_heat_note` | {team} on-ball events, attacking left to right. | Acciones con balón de {team}, atacando de izquierda a derecha. | Actions avec ballon de {team}, attaque de gauche à droite. |
| `ho_spotlight` | Player spotlight | Jugador destacado | Joueur à la une |
| `ho_spot_sentence` | Scored in the showcase match; {g} goals this season. | Marcó en el partido escaparate; {g} goles esta temporada. | A marqué lors du match vitrine ; {g} buts cette saison. |
| `ho_patterns` | Tactical patterns | Patrones tácticos | Schémas tactiques |
| `ho_validated` | Validated | Validado | Validé |
| `ho_teams` | Featured teams | Equipos | Équipes |
| `ho_trust` | Why trust Optix | Por qué confiar en Optix | Pourquoi faire confiance à Optix |
| `ho_trust_1` | The engine computes every number; the language model only writes the sentence. | El motor calcula cada número; el modelo de lenguaje solo escribe la frase. | Le moteur calcule chaque chiffre ; le modèle de langage n'écrit que la phrase. |
| `ho_trust_2` | {n} sentences were held back and rewritten before they were shown. | {n} frases se retuvieron y reescribieron antes de mostrarse. | {n} phrases ont été retenues et réécrites avant d'être affichées. |
| `ho_trust_3` | Every insight opens the events it rests on. | Cada clave abre los eventos en los que se apoya. | Chaque point clé ouvre les événements sur lesquels il repose. |
| `ho_how` | See how it works | Ver cómo funciona | Voir comment ça marche |
| `hp_pat_bait_switch` | Play gathers on one side, then the ball goes to the far side. | El juego se acumula en un lado y luego el balón va al lado contrario. | Le jeu se concentre d'un côté, puis le ballon part de l'autre. |
| `hp_pat_cutback` | Passes pulled back from the byline into the box. | Pases atrás desde la línea de fondo hacia el área. | Passes en retrait depuis la ligne de but vers la surface. |
| `hp_pat_flank_isolation` | Long spells of possession on one touchline. | Largas fases de posesión pegadas a una banda. | Longues séquences de possession le long d'une ligne de touche. |
| `hp_pat_counter_press` | Ball lost high up and won back within seconds. | Balón perdido arriba y recuperado en pocos segundos. | Ballon perdu haut et récupéré en quelques secondes. |
| `hp_pat_starved_finisher` | A forward with few touches who still gets shots away unpressed. | Un delantero con pocos toques que aun así remata sin presión. | Un attaquant avec peu de ballons qui tire tout de même sans pression. |
| `hp_pat_tactical_fouling` | Fouls in the middle third soon after losing the ball. | Faltas en el tercio central poco después de perder el balón. | Fautes dans le tiers central peu après la perte du ballon. |
| `hp_pat_direct_transition` | From a regain in the own half to a shot in seconds. | De una recuperación en campo propio a un tiro en segundos. | D'une récupération dans son camp à un tir en quelques secondes. |
| `hp_pat_press_resistant` | Completes more passes under pressure than team-mates. | Completa más pases bajo presión que sus compañeros. | Réussit plus de passes sous pression que ses coéquipiers. |
| `hp_pat_pressed_presser` | Presses hard, yet its own pressed passes near goal go astray. | Presiona mucho, pero sus pases presionados cerca de su portería se pierden. | Presse fort, mais ses passes sous pression près de son but se perdent. |
| `search` | Search | Buscar | Rechercher |
| `search_label` | Search teams, players and fixtures | Buscar equipos, jugadores y partidos | Rechercher équipes, joueurs et matchs |
| `search_teams` | Teams | Equipos | Équipes |
| `search_players` | Players | Jugadores | Joueurs |
| `search_fixtures` | Fixtures | Partidos | Matchs |
| `search_count` | {n} results | {n} resultados | {n} résultats |
| `search_none` | No result for this search. | Ningún resultado para esta búsqueda. | Aucun résultat pour cette recherche. |
| `search_hint` | Arrows to move, Enter to open, Escape to close. | Flechas para moverse, Intro para abrir, Escape para cerrar. | Flèches pour se déplacer, Entrée pour ouvrir, Échap pour fermer. |
| `search_mw` | Matchweek {n} | Jornada {n} | Journée {n} |
| `fav_follow` | Follow {name} | Seguir a {name} | Suivre {name} |
| `fav_following` | Following | Siguiendo | Suivis |
| `fav_clear` | Clear favourites | Borrar favoritos | Effacer les favoris |
| `fav_note` | Favourites stay in this browser only. | Los favoritos se quedan solo en este navegador. | Les favoris restent uniquement dans ce navigateur. |
| `fav_none` | Nothing followed here yet: use the star on a card. | Aún no sigues nada aquí: usa la estrella de una tarjeta. | Rien de suivi ici pour l'instant : utilisez l'étoile d'une carte. |
| `fav_title` | Favourites | Favoritos | Favoris |
| `pm_forward` | Forward pass | Pase hacia delante | Passe vers l'avant |
| `pm_progressive` | Progressive pass | Pase progresivo | Passe progressive |
| `pm_key` | Key pass | Pase clave | Passe clé |
| `pm_type` | Pass type | Tipo de pase | Type de passe |
| `pm_x0` | Start, length | Inicio, largo | Départ, longueur |
| `pm_y0` | Start, width | Inicio, ancho | Départ, largeur |
| `pm_x1` | End, length | Final, largo | Arrivée, longueur |
| `pm_y1` | End, width | Final, ancho | Arrivée, largeur |
| `ch_leg_op` | Open-play chance ({n}) | Ocasión en juego abierto ({n}) | Occasion dans le jeu ({n}) |
| `ch_leg_sp` | Set-piece chance ({n}) | Ocasión a balón parado ({n}) | Occasion sur coup de pied arrêté ({n}) |
| `patterns_none_line` | No player pattern for this player. | Ningún patrón de jugador para este jugador. | Aucun motif de joueur pour ce joueur. |

## Changed keys in i18n.ts

| Key | English | Español | Français |
|---|---|---|---|
| `console_pizza` | Against players in the same position | Frente a jugadores de su misma posición | Face aux joueurs du même poste |
| `con_context_note` | What the plain total hides. | Lo que el total sin más oculta. | Ce que le total brut cache. |

Earlier in this run `board_lineup_note`, `lane_lift_label` and `ss_axis_x` were shortened for the
Team Board word budget (all three languages); see docs/PROGRESS.md "Final UI decisions".
