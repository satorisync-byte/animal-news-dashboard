#!/usr/bin/env python3
"""Aggregatore notizie mondo animale -> data.json + index.html. Uso: python3 aggregate.py"""
import json, re, time, html, calendar, urllib.parse, difflib, os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import feedparser, requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AnimalNewsMVP/1.0"}
HOURS = 72
def gn(q, lang="en"):
    loc = {"en": "hl=en-US&gl=US&ceid=US:en", "it": "hl=it&gl=IT&ceid=IT:it"}[lang]
    return "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:3d") + "&" + loc

FEEDS = [  # (nome, url, autorevolezza 1-3, filtro_rilevanza)
 ("The Guardian Animals", "https://www.theguardian.com/world/animals/rss", 3, False),
 ("The Guardian Wildlife", "https://www.theguardian.com/environment/wildlife/rss", 3, False),
 ("BBC Science & Environment", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", 3, True),
 ("Google News: National Geographic", gn("site:nationalgeographic.com animals"), 3, True),
 ("Mongabay", "https://news.mongabay.com/feed/", 2, True),
 ("Phys.org Plants & Animals", "https://phys.org/rss-feed/biology-news/plants-animals/", 2, False),
 ("Phys.org Ecology", "https://phys.org/rss-feed/biology-news/ecology/", 2, True),
 ("ScienceDaily Animals", "https://www.sciencedaily.com/rss/plants_animals/animals.xml", 2, False),
 ("Smithsonian", "https://www.smithsonianmag.com/rss/science-nature/", 2, True),
 ("Live Science Animals", "https://www.livescience.com/feeds/tag/animals", 2, False),
 ("Popular Science Animals", "https://www.popsci.com/category/animals/feed/", 2, False),
 ("NYT Science", "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", 3, True),
 ("Google News: ANSA", gn("site:ansa.it animali", "it"), 2, True),
 ("Google News: animali (EN)", gn("animal OR zoo OR wildlife"), 1, True),
 ("Google News: Reuters", gn("site:reuters.com animal OR zoo OR wildlife"), 3, True),
 ("Google News: AP", gn("site:apnews.com animal OR zoo OR wildlife"), 3, True),
 ("Google News: zoo nascite", gn("zoo baby animal born"), 1, True),
 ("Google News: viral animal", gn("viral animal video"), 1, True),
 ("Google News: rescue", gn("animal rescued"), 1, True),
 ("Google News: rare species", gn("rare species spotted OR discovered"), 1, True),
 ("Google News: animali (IT)", gn("animali", "it"), 1, True),
 ("Google News: zoo (IT)", gn("zoo cucciolo nato", "it"), 1, True),
 ("Google News: fauna selvatica (IT)", gn("fauna selvatica OR orso OR lupo", "it"), 1, True),
]
AUTH_DOMAINS = {"reuters":3,"apnews":3,"bbc":3,"theguardian":3,"nytimes":3,"nationalgeographic":3,"cnn":3,"washingtonpost":3,
 "ansa":2,"corriere":2,"repubblica":2,"smithsonianmag":2,"phys.org":2,"sciencedaily":2,"mongabay":2,"livescience":2,"npr":3,"independent":2,"sky":2}

# animale canonico (EN key) -> (nome italiano, regex)
ANIMALS = {
 "red panda":("panda rosso",r"red pandas?|panda ross"),"panda":("panda",r"pandas?"),"penguin":("pinguino",r"penguins?|pinguin[oi]"),"otter":("lontra",r"otters?|lontr[ae]"),
 "capybara":("capibara",r"capybaras?|capibar[ae]"),"elephant":("elefante",r"elephants?|elefant[ei]"),"giraffe":("giraffa",r"giraffes?|giraff[ae]"),
 "lion":("leone",r"lions?\b|leon[ei]\b|leonessa"),"tiger":("tigre",r"tigers?|tigr[ei]"),"bear":("orso",r"\bbears?\b|\bors[oai]\b|orsett"),
 "wolf":("lupo",r"\bwol(f|ves)\b|\blup[oia]\b"),"fox":("volpe",r"\bfox(es)?\b|volp[ei]"),"dog":("cane",r"\bdogs?\b|puppy|puppies|\bcan[ei]\b|cucciol"),
 "cat":("gatto",r"\bcats?\b|kitten|gatt[oi]|gattin"),"monkey":("scimmia",r"monkeys?|macaque|scimmi[ae]|lemur"),
 "gorilla":("gorilla",r"gorillas?"),"chimpanzee":("scimpanzé",r"chimp(anzee)?s?|scimpanz"),"orangutan":("orango",r"orangutans?|orang"),
 "whale":("balena",r"whales?|balen[ae]|orcas?"),"dolphin":("delfino",r"dolphins?|delfin[oi]"),"shark":("squalo",r"sharks?|squal[oi]"),
 "seal":("foca",r"\bseals?\b|\bfoc[ah]e?\b|sea lion"),"turtle":("tartaruga",r"turtles?|tortoises?|tartarug"),"octopus":("polpo",r"octopus|polp[oi]"),
 "crocodile":("coccodrillo",r"crocodiles?|alligators?|coccodrill"),"snake":("serpente",r"snakes?|python|cobra|serpent|vipera"),
 "frog":("rana",r"\bfrogs?\b|\bran[ae]\b|toads?"),"koala":("koala",r"koalas?"),"kangaroo":("canguro",r"kangaroos?|cangur"),
 "sloth":("bradipo",r"sloths?|bradip"),"hippo":("ippopotamo",r"hippos?|hippopotam|ippopotam"),"rhino":("rinoceronte",r"rhinos?|rhinoceros|rinoceront"),
 "zebra":("zebra",r"zebras?"),"horse":("cavallo",r"horses?|pony|cavall[oi]"),"cow":("mucca",r"\bcows?\b|cattle|mucc[ah]e?|bovin"),
 "pig":("maiale",r"\bpigs?\b|maial|\bboars?\b|cinghial"),"goat":("capra",r"goats?|capr[ae]\b"),"sheep":("pecora",r"sheep|pecor"),
 "owl":("gufo",r"\bowls?\b|gufo|civett"),"eagle":("aquila",r"eagles?|aquil[ae]"),"parrot":("pappagallo",r"parrots?|pappagall|cockatoo"),
 "bird":("uccello",r"\bbirds?\b|uccell|flamingo|stork|cicogn"),"bee":("ape",r"\bbees?\b|\bap[ei]\b"),"butterfly":("farfalla",r"butterfl|farfall"),
 "spider":("ragno",r"spiders?|ragn[oi]"),"ant":("formica",r"\bants?\b|formich"),"bat":("pipistrello",r"\bbats?\b|pipistrell"),
 "deer":("cervo",r"\bdeer\b|cerv[oi]|moose|elk|caprioli"),"squirrel":("scoiattolo",r"squirrels?|scoiattol"),"raccoon":("procione",r"raccoons?|procion"),
 "hedgehog":("riccio",r"hedgehogs?"),"rabbit":("coniglio",r"rabbits?|bunn(y|ies)|conigli"),"mouse":("topo",r"\bmice\b|\bmouse\b|\brats?\b|\btop[oi]\b"),
 "jaguar":("giaguaro",r"jaguars?|giaguar"),"leopard":("leopardo",r"leopards?|cheetahs?|ghepard|leopard"),"lynx":("lince",r"\blynx\b|\blinc[ei]\b"),
 "fish":("pesce",r"\bfish\b|salmon|\bpesc[ei]\b"),"jellyfish":("medusa",r"jellyfish|medus[ae]"),"dinosaur":("dinosauro",r"dinosaurs?|dinosaur"),
 "insect":("insetto",r"insects?|beetle|insett"),"camel":("cammello",r"camels?|cammell"),"donkey":("asino",r"donkeys?|asin[oi]"),
}
ANIMAL_RE = {k: re.compile(v[1], re.I) for k, v in ANIMALS.items()}
GENERIC = re.compile(r"animal|wildlife|zoo|species|fauna|creature|pet\b|vet|habitat|endangered|extinct|biodivers|marine life|safari|"
                     r"animal[ei]|faun|specie|bracconag|poach|ornith|mammal|mammifer|reptil|predator", re.I)
CUTE = {"panda","penguin","otter","capybara","koala","sloth","hippo","cat","dog","seal","red panda","hedgehog","raccoon","giraffe","elephant","fox","owl","rabbit","squirrel","octopus","frog","monkey","gorilla","orangutan","bear"}
KW = {
 "bebè": (r"\bbab(y|ies)\b|newborn|\bborn\b|birth|calf|cub|chick|hatch|nato|nata|nascit|cucciol|piccol", 18),
 "virale": (r"viral|video|tiktok|internet|social media|virale|famous|celebrity|star\b|beloved", 15),
 "insolito": (r"bizarre|weird|unusual|strange|funny|hilarious|surpris|curious|mystery|escaped|loose|on the run|strano|curios|fug[ai]|insolit|incredibil", 14),
 "record": (r"first[- ]ever|\bfirst\b|record|oldest|largest|biggest|smallest|rare|new species|discovered|primo|prima volta|record|rar[oi]|nuova specie|scopert", 12),
 "salvataggio": (r"rescue|saved|survives?|reunite|adopt|salvat|soccors|recuper", 10),
 "nome": (r"\bnamed\b|\bnicknamed\b|chiamat[oa]|battezzat", 10),
}
KW_RE = {k: (re.compile(p, re.I), w) for k, (p, w) in KW.items()}
NAME_RE = re.compile(r"(?:named|nicknamed|called|chiamat[oa]|battezzat[oa])\s+['\"“‘]?([A-Z][a-zà-ù]+(?:\s[A-Z][a-zà-ù]+)?)")
LEAD_NAME_RE = re.compile(r"(?:^|:\s*)([A-Z][a-zà-ù]{2,14}),\s+(?:the|il|la|lo)\s")
SAD_RE = re.compile(r"\bdie[sd]?\b|dead|death|killed|kills|mauled|attack|shot|culled|poison|massacre|mort[oai]\b|uccis|sbranat|attacc|abbattut", re.I)
QUOTED_RE = re.compile(r"['\"“‘]([A-Z][a-zà-ù]{2,14})['\"”’]")
STOP = set("the a an of in on to and for is are with at by from as its after new how why what il lo la i gli le di da in con su per tra fra un una che e è del della dei delle al alla".split())

def fetch(feed):
    name, url, auth, filt = feed
    try:
        r = requests.get(url, headers=UA, timeout=20)
        d = feedparser.parse(r.content)
        return feed, r.status_code, d.entries
    except Exception as e:
        return feed, str(e)[:60], []

def entry_time(e):
    for k in ("published_parsed", "updated_parsed"):
        if e.get(k): return calendar.timegm(e[k])
    return None

def clean(s): return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s or ""))).strip()

def find_animal(text):
    best, pos = None, 10**9
    for k, rx in ANIMAL_RE.items():
        m = rx.search(text)
        if m and m.start() < pos: best, pos = k, m.start()
    return best

def norm_title(t): return " ".join(w for w in re.findall(r"[a-zà-ù0-9]+", t.lower()) if w not in STOP)

def dex_check(ticker):
    try:
        r = requests.get("https://api.dexscreener.com/latest/dex/search", params={"q": ticker}, headers=UA, timeout=10)
        pairs = r.json().get("pairs") or []
        hits = [p for p in pairs if p.get("chainId") == "solana" and (p.get("baseToken", {}).get("symbol", "").upper() == ticker)]
        return len(hits)
    except Exception:
        return None

def make_token(s):
    an = s["animal"] or "animal"; it = ANIMALS.get(an, ("animale",))[0]
    nm = s.get("named")
    tags = s["tags"]
    if nm:
        name = f"{nm} the {an.title()}"; base = re.sub(r"[^A-Z]", "", nm.upper())
    else:
        pref = "Baby " if "bebè" in tags else ("Rescue " if "salvataggio" in tags else ("Viral " if "virale" in tags else ""))
        name = f"{pref}{an.title()}".strip(); base = re.sub(r"[^A-Z]", "", ((pref[:1] if pref else "") + an).upper())
    if "tragica" in tags: name += " (notizia tragica: valuta l'opportunità)"
    tick = base[:6] if len(base) >= 3 else (base + "INU")[:5]
    lab = {"bebè":"un cucciolo appena nato","salvataggio":"un salvataggio","virale":"un fenomeno virale","insolito":"una storia insolita","record":"un evento raro o da record"}
    hook = next((lab[t] for t in tags if t in lab), "una notizia del giorno")
    desc = (f"Memecoin ispirata a {nm}, protagonista di {hook} (animale: {it}). " if nm else f"Memecoin ispirata a {hook} con protagonista: {it}. ") + "Idea community-driven, nessun valore intrinseco."
    return {"nome": name, "ticker": "$" + tick, "descrizione": desc}

def main():
    now = time.time(); cutoff = now - HOURS * 3600
    with ThreadPoolExecutor(12) as ex: res = list(ex.map(fetch, FEEDS))
    report, items = [], []
    for (name, url, auth, filt), status, entries in res:
        recent = 0
        for e in entries:
            t = entry_time(e)
            if not t or t < cutoff or t > now + 3600: continue
            title = clean(e.get("title")); summ = clean(e.get("summary"))[:400]
            src = name; link = e.get("link", "")
            if "news.google.com" in url:
                st = e.get("source", {}) or {}
                src = st.get("title") or (title.rsplit(" - ", 1)[-1] if " - " in title else name)
                if " - " in title: title = title.rsplit(" - ", 1)[0]
                summ = ""  # sommari GN sono solo link
                href = (st.get("href") or "").lower()
                auth = max([v for k, v in AUTH_DOMAINS.items() if k in href] + [1])
            text = title + " " + summ
            animal = find_animal(text)
            if filt and not animal and not GENERIC.search(text): continue
            recent += 1
            items.append(dict(title=title, summary=summ, link=link, source=src, feed=name, auth=auth, ts=t, animal=animal, text=text))
        report.append({"feed": name, "url": url, "status": status, "totali": len(entries), "recenti_rilevanti": recent, "ok": recent > 0})
    # dedupe URL
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: -x["auth"]):
        u = it["link"].split("?")[0]
        if u in seen: continue
        seen.add(u); uniq.append(it)
    # cluster titoli simili
    clusters = []
    for it in uniq:
        nt = norm_title(it["title"]); ws = set(nt.split())
        for c in clusters:
            inter = len(ws & c["ws"]) / max(1, min(len(ws), len(c["ws"])))
            if difflib.SequenceMatcher(None, nt, c["nt"]).ratio() > 0.72 or (inter >= 0.6 and len(ws & c["ws"]) >= 4):
                c["items"].append(it); break
        else: clusters.append({"nt": nt, "ws": ws, "items": [it]})
    stories = []
    for c in clusters:
        its = sorted(c["items"], key=lambda x: (-x["auth"], -x["ts"]))
        lead = its[0]; text = " ".join(i["text"] for i in its)
        srcs = sorted({i["source"] for i in its})
        animal = lead["animal"] or find_animal(text)
        # Impatto
        n = len(srcs); maxauth = max(i["auth"] for i in its)
        age_h = (now - max(i["ts"] for i in its)) / 3600
        vis = min(50, 14 * (n - 1) + (8 if n > 1 else 0)); authp = {1: 8, 2: 16, 3: 25}[maxauth]
        rec = max(0, 25 * (1 - age_h / HOURS))
        impact = round(min(100, vis + authp + rec))
        # Meme
        tags = [k for k, (rx, w) in KW_RE.items() if rx.search(text)]
        m = NAME_RE.search(text) or LEAD_NAME_RE.search(lead["title"]) or QUOTED_RE.search(lead["title"])
        named = m.group(1) if m else None
        if named and named.lower() in STOP | {"zoo", "the"}: named = None
        if named and "nome" not in tags: tags.append("nome")
        meme = sum(KW_RE[t][1] for t in tags if t in KW_RE) + (10 if named and "nome" in tags and not NAME_RE.search(text) else 0)
        meme += 20 if animal in CUTE else (10 if animal else 0)
        if SAD_RE.search(lead["title"]): meme *= 0.5; tags.append("tragica")
        meme = round(min(100, meme))
        overall = round(0.45 * impact + 0.55 * meme)
        stories.append(dict(titolo=lead["title"], sommario=lead["summary"], link=lead["link"], fonte=lead["source"],
            fonti=srcs, n_fonti=n, altri_link=[{"fonte": i["source"], "link": i["link"]} for i in its[1:6]],
            data=datetime.fromtimestamp(lead["ts"], timezone.utc).isoformat(), ore_fa=round(age_h, 1),
            animal=animal, animale=ANIMALS[animal][0] if animal else "generico", named=named, tags=tags,
            impatto=impact, meme=meme, punteggio=overall))
    stories.sort(key=lambda s: -s["punteggio"])
    for s in stories[:30]:
        s["token"] = make_token(s)
    with ThreadPoolExecutor(6) as ex:
        hits = list(ex.map(dex_check, [s["token"]["ticker"][1:] for s in stories[:30]]))
    for s, h in zip(stories[:30], hits):
        s["token"]["dex_solana"] = h  # None = controllo fallito
    out = {"generato": datetime.now(timezone.utc).isoformat(), "finestra_ore": HOURS, "feed": report, "storie": stories}
    json.dump(out, open("data.json", "w"), ensure_ascii=False, indent=1)
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html"), encoding="utf-8").read()
    open("index.html", "w", encoding="utf-8").write(tpl.replace("/*DATA*/null", json.dumps(out, ensure_ascii=False).replace("</", "<\\/")))
    ok = [r for r in report if r["ok"]]
    print(f"Feed funzionanti: {len(ok)}/{len(report)}")
    for r in report: print(("  OK " if r["ok"] else "  KO ") + f"{r['feed']}: status={r['status']} tot={r['totali']} recenti={r['recenti_rilevanti']}")
    print(f"Storie: {len(stories)} -> index.html, data.json")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__))); main()
