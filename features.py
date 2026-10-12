"""Funzioni aggiuntive: storico/trend, immagini, Google Trends, nomi token, controllo Solana (DexScreener + pump.fun)."""
import json, re, time, hashlib, html, os, math, zlib
from concurrent.futures import ThreadPoolExecutor
import requests, feedparser

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AnimalNewsMVP/1.1"}
STATUS = {}  # esito servizi esterni -> mostrato nel footer

def h8(s): return hashlib.sha1(s.encode("utf-8", "ignore")).hexdigest()[:8]
def url_key(u): return h8((u or "").split("?")[0].split("#")[0].rstrip("/"))

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default
def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))

# ---------------- 1. Storico / trend ----------------
HIST_DAYS = 7
def assign_ids(clusters_urls, hist):
    """clusters_urls: lista di liste di URL. Riusa l'id storico se un URL coincide, altrimenti id nuovo da URL principale."""
    idx = {}
    for sid, e in hist.get("storie", {}).items():
        for k in e.get("u", []): idx.setdefault(k, sid)
    out, used = [], set()
    for urls in clusters_urls:
        keys = [url_key(u) for u in urls]
        sid = next((idx[k] for k in keys if k in idx and idx[k] not in used), None) or keys[0]
        while sid in used: sid = h8(sid + "x")
        used.add(sid); out.append((sid, keys))
    return out

def trend_for(entry, n_now, now):
    """Restituisce (stato, delta_fonti_6h, delta_punteggio_6h, serie)."""
    pts = entry.get("h", []) if entry else []
    if not pts or now - pts[0][0] < 3 * 3600:
        first = pts[0][0] if pts else now
        return ("nuova" if now - first < 3 * 3600 else "stabile"), 0, 0, pts
    ref = [p for p in pts if p[0] <= now - 6 * 3600]
    base = ref[-1] if ref else pts[0]
    dn = n_now - base[1]; ds = pts[-1][2] - base[2] if pts else 0
    return ("crescita" if dn >= 1 or ds >= 6 else "stabile"), dn, ds, pts

def update_history(hist, stories, now):
    st = hist.setdefault("storie", {}); cut = now - HIST_DAYS * 86400
    for s in stories:
        e = st.setdefault(s["id"], {"t": s["titolo"][:80], "u": [], "h": []})
        e["u"] = list(dict.fromkeys(e["u"] + s["_keys"]))[-12:]
        p = [int(now), s["n_fonti"], s["punteggio"]]
        if not e["h"] or e["h"][-1][1:] != p[1:] or now - e["h"][-1][0] > 6 * 3600: e["h"].append(p)
        e["h"] = e["h"][-40:]
    for sid in list(st):
        st[sid]["h"] = [p for p in st[sid]["h"] if p[0] >= cut]
        if not st[sid]["h"]: del st[sid]
    hist["aggiornato"] = int(now)
    return hist

# ---------------- 5. Immagini ----------------
IMG_RE = re.compile(r'<img[^>]+src="([^"]+)"', re.I)
def entry_image(e):
    for k in ("media_content", "media_thumbnail"):
        for m in e.get(k) or []:
            u = m.get("url")
            if u and (k == "media_thumbnail" or "image" in (m.get("type") or "image") or re.search(r"\.(jpe?g|png|webp)", u, re.I)): return u
    for l in e.get("enclosures") or e.get("links") or []:
        if (l.get("type") or "").startswith("image") and l.get("href"): return l["href"]
    for c in [e.get("summary", "")] + [x.get("value", "") for x in e.get("content") or []]:
        m = IMG_RE.search(c or "")
        if m and not m.group(1).startswith("data:") and "feeds.feedburner" not in m.group(1): return html.unescape(m.group(1))
    return None

OG_RE = re.compile(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]*content=["\']([^"\']+)', re.I)
OG_RE2 = re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)', re.I)
def og_image(url):
    try:
        r = requests.get(url, headers=UA, timeout=6, stream=True)
        if "news.google.com" in r.url: return None
        buf = b""
        for chunk in r.iter_content(16384):
            buf += chunk
            if len(buf) > 300000 or b"</head>" in buf: break
        r.close(); t = buf.decode("utf-8", "ignore")
        m = OG_RE.search(t) or OG_RE2.search(t)
        if m:
            u = html.unescape(m.group(1))
            if u.startswith("//"): u = "https:" + u
            if u.startswith("http") and "googleusercontent" not in u and "gstatic" not in u: return u
    except Exception: pass
    return None

BUA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}
def gn_decode(u):
    """Risolve un link news.google.com/rss/articles/... nell'URL dell'articolo (endpoint pubblico batchexecute)."""
    try:
        aid = u.split("/articles/")[1].split("?")[0]
        r = requests.get("https://news.google.com/rss/articles/" + aid, headers=BUA, timeout=6)
        sg = re.search(r'data-n-a-sg="([^"]+)"', r.text); ts = re.search(r'data-n-a-ts="([^"]+)"', r.text)
        if not (sg and ts): return None
        req = ["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{aid}",{ts.group(1)},"{sg.group(1)}"]']
        r2 = requests.post("https://news.google.com/_/DotsSplashUi/data/batchexecute", headers={**BUA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                           data="f.req=" + requests.utils.quote(json.dumps([[req]])), timeout=6)
        out = json.loads(json.loads(r2.text.split("\n\n")[1])[0][2])[1]
        return out if out.startswith("http") else None
    except Exception: return None

def add_og_images(stories, cache, limit=60):
    imgc = cache.setdefault("img", {}); todo = []
    for s in stories[:limit]:
        if s.get("img"): continue
        cands = [s["link"]] + [o["link"] for o in s.get("altri_link", [])] + ([s["link_esterno"]] if s.get("link_esterno") else [])
        cands = [u for u in cands if u and "reddit.com/r/" not in u][:2]
        k = url_key(s["link"])
        if k in imgc: s["img"] = imgc[k][0] or None; continue
        todo.append((s, k, cands))
    def work(t):
        s, k, cands = t
        for u in cands:
            if "news.google.com/rss/articles/" in u: u = gn_decode(u)
            if not u or "news.google.com" in u: continue
            im = og_image(u)
            if im: return im
        return None
    with ThreadPoolExecutor(10) as ex: res = list(ex.map(work, todo))
    for (s, k, _), im in zip(todo, res):
        s["img"] = im; imgc[k] = [im or "", int(time.time())]
    STATUS["og_image"] = f"{sum(1 for r in res if r)}/{len(res)} nuove immagini og:image"

# ---------------- 3. Google Trends ----------------
def google_trends():
    out = []; st = []
    for geo in ("US", "IT"):
        try:
            r = requests.get(f"https://trends.google.com/trending/rss?geo={geo}", headers=UA, timeout=12)
            if r.status_code != 200: st.append(f"{geo}: HTTP {r.status_code}"); continue
            items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
            for it in items:
                g = lambda tag: clean_tag((re.search(rf"<{tag}>(.*?)</{tag}>", it, re.S) or [None, ""])[1])
                term = g("title")
                out.append({"term": term, "geo": geo, "traffic": g("ht:approx_traffic"),
                            "news": " | ".join(clean_tag(x) for x in re.findall(r"<ht:news_item_title>(.*?)</ht:news_item_title>", it, re.S)),
                            "link": f"https://trends.google.com/trends/explore?geo={geo}&date=now%201-d&q=" + requests.utils.quote(term)})
            st.append(f"{geo}: OK ({len(items)} ricerche)")
        except Exception as ex:
            st.append(f"{geo}: errore {str(ex)[:40]}")
    STATUS["google_trends"] = "; ".join(st)
    return out

def clean_tag(s): return re.sub(r"<[^>]+>", "", html.unescape(s or ""))

def trends_match(s, trends, animal_terms):
    """Corrispondenza se il termine di tendenza compare nel titolo, o se contiene il nome dell'animale/individuo."""
    text = s["titolo"].lower()
    keys = [k.lower() for k in animal_terms if k and len(k) >= 3]
    for t in trends:
        term = t["term"].lower().strip()
        if not term: continue
        if (len(term) >= 5 and re.search(r"\b" + re.escape(term) + r"\b", text)) or any(re.search(r"\b" + re.escape(k) + r"s?\b", term) for k in keys):
            return t
    return None

# ---------------- 4. Nomi token ----------------
PUNS = {
 "penguin":["Pengwin","Pump-guin","Waddle"],"otter":["Otterly","Hotter","Otter Space"],"cat":["Purrfect","Catnip","Meowney"],"dog":["Doggo","Pupper","Woof"],
 "bear":["Unbearable","Bearly","Fuzzy Bear"],"panda":["Pandamonium","Bamboo","Pandemic Panda"],"red panda":["Firefox","Red Pandamonium","Ailurus"],
 "whale":["Whale Alert","Big Splash","Moby"],"owl":["Hoot","Owl Street","Night Owl"],"bee":["Bee-lieve","Buzz","Honey Pump"],"frog":["Ribbit","Toad-ally","Hopium"],
 "seal":["Seal the Deal","Sealy","Seal Team"],"sloth":["Slothy","Slow Pump","Lazy Sloth"],"capybara":["Capy","Okay Capy","Capybro"],"hippo":["Hippo-Hop","Hipster Hippo","Chonk"],
 "giraffe":["Giraf","Tall Order","Neck Level"],"fox":["Foxy","Fox Trot","What Does the Fox"],"wolf":["Wolfpack","Howl","Lone Wolf"],"shark":["Sharky","Jaws","Fin Tech"],
 "elephant":["Trunk","Ellie","Memephant"],"lion":["Lionheart","Roar","King Leo"],"tiger":["Tigro","Tiger King","Eye of Tiger"],"koala":["Koalafied","Eucaly","Drop Bear"],
 "cow":["Moo","Moo-n","Holy Cow"],"pig":["Oink","Piggy Bank","Hog Wild"],"goat":["GOAT","Billy","Kid"],"sheep":["Baa","Woolly","Shear"],"horse":["Neigh","Hay","Stallion"],
 "rabbit":["Hop","Bunny Hop","Carrot"],"turtle":["Shell","Slow and Steady","Turtly"],"octopus":["Inkfluencer","Eight Arms","Tentacool"],"crocodile":["Crocoin","Snappy","Later Gator"],
 "snake":["Hiss","Sssnek","Noodle"],"bat":["Batcoin","Night Flyer","Fang"],"deer":["Oh Deer","Bambi","Antler"],"raccoon":["Trash Panda","Bandit","Rocket"],"dolphin":["Flipper","Click","Echo"],
 "monkey":["Banana","Ape Mode","Monke"],"chimpanzee":["Chimpion","Monke","Banana"],"gorilla":["Harambe Jr","Silverback","Gorilla Glue"],"orangutan":["Orange Ape","Jungle Man","Ginger"],
 "parrot":["Polly","Squawk","Copycat Parrot"],"eagle":["Freedom","Soar","Talon"],"bird":["Tweet","Birb","Early Bird"],"squirrel":["Nuts","Squirrely","Acorn"],"hedgehog":["Spiky","Sonic Hog","Hoglet"],
 "mouse":["Squeak","Cheese","Tiny Rat"],"jaguar":["Jag","Spots","Panthera"],"leopard":["Spots","Leo Pard","Speedy"],"lynx":["Lynx Link","Tufty","Lynxie"],"fish":["Fishy","Gill","Blub"],
 "jellyfish":["Jelly","Wobble","Sting"],"dinosaur":["Dino","Rawr","Jurassic"],"insect":["Buggy","Bug Out","Antenna"],"camel":["Hump Day","Dromedary","Camelot"],"donkey":["Hee Haw","Donk","Mule"],
 "kangaroo":["Roo","Jumpy","Pouch"],"rhino":["Horny Rhino","Rhino Run","Chonk"],"zebra":["Stripes","Zeb","Barcode"],"spider":["Webby","Spidey","Eight Legs"],"ant":["Antsy","Colony","Tiny Ant"],
 "butterfly":["Flutter","Monarch","Chrysalis"],"turtle ":["Shell"],"animal":["Critter","Zoo Mode","Wild Card"],
}
EVENT = {"bebè":["Baby","Cub","Bimbo"],"virale":["Viral","Meme","Pump"],"insolito":["Mad","Weird","Pazzo"],"record":["Rare","Mega","King"],"salvataggio":["Hero","Saved","Salvo"]}
SUFFIX = ["Inu","Coin","Wif Hat","Cat","Moon","Bonk"]
IT_DIM = lambda w: (w[:-1] if w[-1] in "aeio" else w) + "ino"
EV_IT = {"bebè":"un cucciolo appena nato","salvataggio":"un salvataggio","virale":"un fenomeno virale","insolito":"una storia insolita","record":"un evento raro o da record","nome":"un animale diventato famoso"}

def portmanteau(a, b):
    a, b = a.replace(" ", ""), b.replace(" ", "")
    for k in range(min(len(a), len(b)) - 1, 1, -1):  # sovrapposizione finale/iniziale
        if a.lower().endswith(b.lower()[:k]): return (a + b[k:]).title()
    return (a[:max(3, math.ceil(len(a) * 0.6))] + b[-max(3, len(b) // 2):].lower()).title()

def mk_ticker(name, used):
    w = [x for x in re.sub(r"[^A-Za-z ]", "", name).upper().split() if x not in ("THE", "IL", "LA", "OF")]
    cands = []
    if w:
        j = "".join(w); w1 = w[-1] if len(w) > 1 else ""
        cands += [j if 3 <= len(j) <= 6 else None, (w[0][:6 - len(w1)] + w1) if w1 and len(w1) <= 3 else None, (w[0][0] + w1) if w1 and len(w1) <= 5 else None,
                  w[0] if 3 <= len(w[0]) <= 6 else None, "".join(x[0] for x in w) if len(w) >= 3 else None, (w[0][:3] + w1[:3]) if w1 else None, j[:5], j[:4]]
    for c in cands:
        if c and 3 <= len(c) <= 6 and c not in used: used.add(c); return c
    c = (re.sub(r"[^A-Z]", "", name.upper()) + "INU")[:5]
    while c in used: c = c[:-1] + chr(65 + (ord(c[-1]) - 64) % 26)
    used.add(c); return c

def token_ideas(s, ANIMALS, seed):
    an = s["animal"] or "animal"; it = ANIMALS.get(an, ("animale",))[0]; nm = s.get("named"); tags = s["tags"]
    A = an.title(); ev_tags = [t for t in tags if t in EVENT] or ["virale"]
    pool = []
    if nm:
        pool += [(f"{nm} the {A}", "nome"), (f"{nm} {SUFFIX[seed % 6]}", "nome+suffisso"), (portmanteau(nm, an), "portmanteau nome+animale"), (f"{nm} Wif Hat", "meme wif")]
    puns = PUNS.get(an, PUNS["animal"])
    pool += [(puns[seed % len(puns)], "gioco di parole"), (puns[(seed + 1) % len(puns)] + " " + SUFFIX[(seed + 2) % 6], "gioco di parole+suffisso")]
    for t in ev_tags[:2]:
        w = EVENT[t][seed % 3]
        pool += [(f"{w} {A}", "evento+animale"), (portmanteau(w, an), "portmanteau evento+animale")]
    pool += [(f"{IT_DIM(it.split()[0]).title()} {SUFFIX[(seed + 3) % 6]}", "mix italiano/inglese"), (f"{A} {SUFFIX[(seed + 4) % 6]}", "animale+suffisso meme")]
    order = ["nome", "gioco di parole", "portmanteau nome+animale", "mix italiano/inglese", "evento+animale", "portmanteau evento+animale", "gioco di parole+suffisso", "nome+suffisso", "animale+suffisso meme", "meme wif"]
    pool.sort(key=lambda x: order.index(x[1]))
    # varia: garantisci tipi diversi
    pick, seen_t = [], set()
    for n, t in pool:
        key = n.lower()
        if key in {p[0].lower() for p in pick} or t.split("+")[0] in seen_t: continue
        pick.append((n, t)); seen_t.add(t.split("+")[0])
        if len(pick) == 3: break
    for n, t in pool:
        if len(pick) >= 3: break
        if n.lower() not in {p[0].lower() for p in pick}: pick.append((n, t))
    used, out = set(), []
    hook = next((EV_IT[t] for t in tags if t in EV_IT), "una notizia del giorno")
    for n, t in pick:
        tk = mk_ticker(n, used)
        d = f"{t.capitalize()}: ispirata a {nm} ({it}), protagonista di {hook}." if nm else f"{t.capitalize()}: celebra {hook} (animale: {it})."
        out.append({"nome": n, "ticker": "$" + tk, "descrizione": d, "tipo": t})
    return out

def llm_ideas(s):
    key = os.environ.get("OPENAI_API_KEY")
    if not key: return None
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}"}, timeout=20, json={
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": "Notizia: " + s["titolo"] + "\nProponi 3 nomi creativi di memecoin (giochi di parole, portmanteau). JSON: {\"idee\":[{\"nome\":..,\"ticker\":3-6 lettere maiuscole,\"descrizione\":1 frase in italiano}]}"}]})
        ids = json.loads(r.json()["choices"][0]["message"]["content"])["idee"][:3]
        return [{"nome": i["nome"], "ticker": "$" + re.sub(r"[^A-Z]", "", i["ticker"].upper())[:6], "descrizione": i["descrizione"], "tipo": "LLM"} for i in ids]
    except Exception: return None

# ---------------- 2. Controllo Solana ----------------
TTL = 3 * 3600
class Solana:
    def __init__(self, cache):
        self.c = cache.setdefault("sol", {}); self.ok = {"dex": [0, 0], "pump": [0, 0]}; self.last = 0
    def _get(self, kind, url, params, reduce=lambda d: d):
        k = kind + ":" + json.dumps(params, sort_keys=True)
        hit = self.c.get(k)
        if hit and time.time() - hit[0] < TTL: return hit[1]
        self.ok[kind][1] += 1
        for attempt in range(2):
            wait = 0.25 - (time.time() - self.last)
            if wait > 0: time.sleep(wait)
            self.last = time.time()
            try:
                h = dict(UA); 
                if kind == "pump": h.update({"Origin": "https://pump.fun", "Accept": "application/json"})
                r = requests.get(url, params=params, headers=h, timeout=10)
                if r.status_code == 429: time.sleep(3); continue
                if r.status_code != 200: break
                data = reduce(r.json()); self.ok[kind][0] += 1
                self.c[k] = [int(time.time()), data]; return data
            except Exception: break
        return None
    def dex(self, q):
        red = lambda d: [{"baseToken": {k: p.get("baseToken", {}).get(k) for k in ("name", "symbol", "address")}, "liquidity": {"usd": (p.get("liquidity") or {}).get("usd")},
                          "volume": {"h24": (p.get("volume") or {}).get("h24")}, "pairCreatedAt": p.get("pairCreatedAt"), "url": p.get("url")}
                         for p in (d.get("pairs") or []) if p.get("chainId") == "solana"]
        return self._get("dex", "https://api.dexscreener.com/latest/dex/search", {"q": q}, red)
    def pump(self, q):
        d = self._get("pump", "https://frontend-api-v3.pump.fun/coins", {"searchTerm": q, "limit": 30, "offset": 0, "sort": "created_timestamp", "order": "DESC", "includeNsfw": "false"},
                      lambda d: [{k: c.get(k) for k in ("name", "symbol", "mint", "created_timestamp", "usd_market_cap")} for c in d] if isinstance(d, list) else None)
        return d

def _pair(p, now):
    b = p.get("baseToken", {}); age = (now - p["pairCreatedAt"] / 1000) / 86400 if p.get("pairCreatedAt") else None
    return {"nome": b.get("name"), "ticker": b.get("symbol"), "liq": round((p.get("liquidity") or {}).get("usd") or 0), "vol24": round((p.get("volume") or {}).get("h24") or 0),
            "eta_g": round(age, 1) if age is not None else None, "url": p.get("url"), "fonte": "DexScreener", "addr": b.get("address")}

def solana_check(sol, s, keywords):
    now = time.time(); tick = {t["ticker"][1:].upper() for t in s["tokens"]}; names = {re.sub(r"\s*\(.*", "", t["nome"]).lower() for t in s["tokens"]}
    kws = [k.lower() for k in keywords if k and len(k) >= 3]
    exact, similar, failed = [], [], 0
    queries = list(tick) + list(names) + kws
    for q in dict.fromkeys(queries):
        pairs = sol.dex(q)
        if pairs is None: failed += 1; continue
        for p in pairs:
            b = p.get("baseToken", {}); sym = (b.get("symbol") or "").upper(); nm = (b.get("name") or "").lower()
            if nm in names or (sym in tick and any(k in nm for k in kws)): exact.append(_pair(p, now))
            elif sym in tick: similar.append(_pair(p, now))
            elif any(k in nm or k in sym.lower() for k in kws): similar.append(_pair(p, now))
    pump_ok = None
    for q in dict.fromkeys(kws[:2] + [n for n in names][:1]):
        coins = sol.pump(q)
        if coins is None: pump_ok = pump_ok or False; continue
        pump_ok = True
        for c in coins:
            sym = (c.get("symbol") or "").upper(); nm = (c.get("name") or "").lower()
            age = (now - (c.get("created_timestamp") or 0) / 1000) / 86400
            d = {"nome": c.get("name"), "ticker": c.get("symbol"), "liq": None, "vol24": None, "mcap": round(c.get("usd_market_cap") or 0),
                 "eta_g": round(age, 1), "url": "https://pump.fun/coin/" + c.get("mint", ""), "fonte": "pump.fun", "addr": c.get("mint")}
            if nm in names or (sym in tick and any(k in nm for k in kws)): exact.append(d)
            elif age <= 14 and any(re.search(r"\b" + re.escape(k), nm) or k == sym.lower() for k in kws): similar.append(d)
    def uniq(l):
        seen, o = set(), []
        for x in sorted(l, key=lambda x: -((x.get("liq") or 0) + (x.get("vol24") or 0) + (x.get("mcap") or 0))):
            if x["addr"] in seen: continue
            seen.add(x["addr"]); x.pop("addr", None); o.append(x)
        return o[:6]
    exact, similar = uniq(exact), uniq(similar)
    per_tick = {t: sum(1 for e in exact + similar if (e["ticker"] or "").upper() == t) for t in tick}
    if failed == len(dict.fromkeys(queries)): badge = "Controllo non riuscito"
    elif exact: badge = "Già lanciato"
    elif similar: badge = "Simili esistenti"
    else: badge = "Libero"
    return {"badge": badge, "esatti": exact, "simili": similar, "per_ticker": per_tick, "pump_ok": pump_ok}
