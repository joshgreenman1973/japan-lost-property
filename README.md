# Left behind

What Tokyo loses in a year, and what it gets back. 4,850,775 items and ¥4.5bn (about $30.1m) in
cash handed in to Tokyo police, broken down by what each kind of thing became: returned to the
owner, given to the finder, property of the Metropolitan Government, or thrown away.

Mobile phones go home 83% of the time. Umbrellas, 1.7%.

## Data

- Tokyo Metropolitan Police, [遺失物取扱状況 (Reiwa 7 / 2025)](https://www.keishicho.metro.tokyo.lg.jp/about_mpd/jokyo_tokei/kakushu/kaikei.html)
- National Police Agency, [index of prefectural lost-property searches](https://www.npa.go.jp/bureau/soumu/ishitsubutsu/otoshimono/todofukenishitubutu.html)
- Exchange rate: European Central Bank reference rates via frankfurter.dev

## Rebuild

```
python3 build_japan.py     # -> out_japan/data.json, copy to data/
```

Fails loudly if the police page's table structure changes. Updated once a year, in early March.
See [methodology.html](methodology.html) — especially the note on why the "found" and "reported
lost" series must not be subtracted from each other.
