# papich-bench results

- **Dataset:** `datasets/papich.yaml`
- **Judge:** `google/gemma-4-31b-it:free`
- **Answerers:** nemotron-super, nemotron-ultra, glm-5.2, minimax-m3, duckduckgo
- **Run at:** 2026-09-02T13:40:14+00:00

## Leaderboard

| Rank | Answerer | Score | Judged | Found (avg) | Truthful (avg) | Errors | Latency |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | glm-5.2 | 75% | 1/1 | 1.00 | 2.00 | 0 | 13.8s |
| 2 | duckduckgo | 75% | 1/1 | 1.00 | 2.00 | 0 | 5.5s |
| 3 | nemotron-ultra | 25% | 1/1 | 0.00 | 1.00 | 0 | 34.5s |
| 4 | minimax-m3 | 25% | 1/1 | 0.00 | 1.00 | 0 | 2.3s |
| 5 | nemotron-super | 0% | 1/1 | 0.00 | 0.00 | 0 | 24.2s |

## Per-item breakdown

### papich-bench  _(flow)_

**nemotron-super**

> `who-is-arthas` Q: Who is Arthas in Dota 2?
>
> `who-is-arthas` — found=0 truthful=0
>
> Arthas Menethil is not a playable hero in Dota 2; he is the Warcraft character that inspired the Dota 2 hero Lich.
>
> _found (no):_ The candidate failed to identify the Ukrainian streamer Papich, the Chinese pro player, or the hero Abaddon, which were the primary requirements.
>
> _truthful (no):_ The candidate claims Arthas inspired Lich; however, in the context of Dota 2's Warcraft III origins, the 'Arthas' archetype is primarily associated with Abaddon and Omniknight.
>
> _→ next: stop_


**nemotron-ultra**

> `who-is-arthas` Q: Who is Arthas in Dota 2?
>
> `who-is-arthas` — found=0 truthful=1
>
> Arthas Menethil is not a character in Dota 2. He is a major figure from the Warcraft universe (Warcraft III, World of Warcraft) who becomes the Lich King. Dota 2 does not include any hero named Arthas; the closest thematic parallels are the heroes Lich and Wraith King, but they are distinct characters.
>
> _found (no):_ The candidate failed to identify the streamer Papich, the Chinese pro player, or the hero Abaddon, which were the primary requirements of the prompt.
>
> _truthful (partial):_ While technically correct that there is no hero literally named 'Arthas' in the game files, it is factually incorrect in the context of the Dota 2 community and lore origins (Abaddon) which the question was targeting.
>
> _→ next: stop_


**glm-5.2**

> `who-is-arthas` Q: Who is Arthas in Dota 2?
>
> `who-is-arthas` — found=1 truthful=2
>
> Arthas was the original name of the hero now known as Abaddon in Dota 2. In the original DotA mod for Warcraft III, this hero was based on Arthas Menethil from the Warcraft universe. When Valve created Dota 2, they renamed and redesigned the character to avoid copyright issues with Blizzard. Abaddon is a melee strength hero known for his protective abilities, including Aphotic Shield and his ultimate Borrowed Time, which heals him when he takes damage while active.
>
> _found (partial):_ The candidate identifies the hero Abaddon, but completely fails to mention the Ukrainian streamer Papich, who was the primary requirement.
>
> _truthful (yes):_ The information provided about Abaddon's origins and abilities is factually correct.
>
> _→ next: stop_


**minimax-m3**

> `who-is-arthas` Q: Who is Arthas in Dota 2?
>
> `who-is-arthas` — found=0 truthful=1
>
> Arthas is not a character in Dota 2. Arthas Menethil is a prominent character in the Warcraft universe, created by Blizzard Entertainment. He is the Lich King and serves as a major figure in the Warcraft RTS games and World of Warcraft. The character you may be thinking of is Arthas, the hero from Heroes of the Storm (also by Blizzard), who appears in some Warcraft-themed content, but he is not a Dota 2 hero.
>
> _found (no):_ The candidate answer completely failed to identify the streamer Papich, the Chinese pro player, or the hero Abaddon, which were the primary requirements.
>
> _truthful (partial):_ While it is technically true that there is no character named 'Arthas' in the official Dota 2 roster, it is false to say he is 'not in Dota 2' in the context of the community/meta-game (streamers and players), and it misses the specific community references requested.
>
> _→ next: stop_


**duckduckgo**

> `who-is-arthas` Q: Who is Arthas in Dota 2?
>
> `who-is-arthas` — found=1 truthful=2
>
> Arthas is a professional Dota 2 support player. He is a Chinese player who currently competes for Team LEI. While he has been playing professionally for several years with around 50 professional matches, his career has not yet produced significant championship titles or substantial prize money (approximately $1,450 in total prize earnings).
>
> _found (partial):_ The candidate identifies the Chinese professional player, but completely misses the primary target (Papich) and the hero Abaddon.
>
> _truthful (yes):_ The information provided about the Chinese professional player is factually consistent with the reference's mention of such a person.
>
> _→ next: stop_

