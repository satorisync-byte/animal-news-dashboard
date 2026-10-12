#!/usr/bin/env python3
"""Avvisi Telegram per storie con punteggio >= SOGLIA. Ogni storia viene avvisata una sola volta (alerted_telegram.json)."""
import json, os, time, html, requests
SOGLIA, MAX_PER_RUN, KEEP_DAYS = 65, 5, 10
DASH = "https://satorisync-byte.github.io/animal-news-dashboard/"
TRL = {"crescita": "📈 in crescita", "nuova": "🆕 nuova", "stabile": "➖ stabile"}
E = lambda s: html.escape(str(s or ""), quote=True)

def msg(s):
    link = s.get("link_articolo") or s["link"]
    tr = s.get("trend") or {}; so = s.get("solana") or {}
    lines = ["🐾 <b>Nuova notizia sopra 65</b>", "", f"<b>{E(s['titolo'])}</b>",
             f"Punteggio: <b>{s['punteggio']}</b> (Impatto {s['impatto']} · Meme {s['meme']})",
             f"Fonte: <a href=\"{E(link)}\">{E(s['fonte'])}</a> ({s['n_fonti']} fonti)",
             f"Animale: {E(s.get('animale'))}", f"Andamento: {TRL.get(tr.get('stato'), '—')}",
             f"Solana: {E(so.get('badge') or 'non controllato')}"]
    toks = s.get("tokens") or ([s["token"]] if s.get("token") else [])
    if toks:
        lines += ["", "<b>Idee token:</b>"] + [f"• {E(t['nome'])} <code>{E(t['ticker'])}</code> — {E(t['descrizione'])}" for t in toks[:3]]
    lines += ["", "<i>Solo suggerimenti, non consulenza finanziaria.</i>", f"<a href=\"{DASH}\">Apri la dashboard</a>"]
    return "\n".join(lines)

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    path = "alerted_telegram.json"
    try: st = json.load(open(path))
    except Exception: st = {"alerted": {}}
    now = time.time()
    st["alerted"] = {k: v for k, v in st.get("alerted", {}).items() if now - v.get("ts", 0) < KEEP_DAYS * 86400}
    seen = set(st["alerted"]) | {v.get("link") for v in st["alerted"].values()}
    stories = json.load(open("data.json"))["storie"]
    todo = [s for s in stories if s["punteggio"] >= SOGLIA and s.get("id") not in seen and s["link"] not in seen][:MAX_PER_RUN]
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    print(f"Storie >= {SOGLIA} da avvisare: {len(todo)}")
    if not tok or not chat:
        print("Segreti Telegram mancanti: avvisi saltati."); return
    sent = 0
    for s in todo:
        try:
            r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage", timeout=20,
                              json={"chat_id": chat, "text": msg(s), "parse_mode": "HTML", "disable_web_page_preview": False})
            ok = r.status_code == 200 and r.json().get("ok")
            desc = "" if ok else (r.json().get("description", "") if r.headers.get("content-type", "").startswith("application/json") else "")
            print(f"Telegram sendMessage: HTTP {r.status_code} ok={bool(ok)} {desc[:120]} | {s['titolo'][:70]}")
        except Exception as e:
            ok = False; print(f"Telegram sendMessage: errore di rete {type(e).__name__} | {s['titolo'][:70]}")
        if ok:
            sent += 1
            st["alerted"][s.get("id") or s["link"]] = {"link": s["link"], "titolo": s["titolo"][:120], "punteggio": s["punteggio"], "ts": int(now)}
        time.sleep(1.2)
    st["aggiornato"] = int(now)
    json.dump(st, open(path, "w"), ensure_ascii=False, indent=1)
    print(f"Avvisi inviati: {sent}/{len(todo)}")

if __name__ == "__main__":
    try: main()
    except Exception as e: print(f"notify.py: errore {type(e).__name__}: {str(e)[:120]}")
