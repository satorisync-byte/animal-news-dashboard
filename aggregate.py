#!/usr/bin/env python3
"""Aggregatore notizie mondo animale -> data.json + index.html. Uso: python3 aggregate.py"""
import json, re, math, time, html, calendar, urllib.parse, difflib, os
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import feedparser, requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AnimalNewsMVP/1.0"}
HOURS = 72
def gn(q, lang="en"):
    if isinstance(q, tuple): q, lang = q
    loc = {"en": "hl=en-US&gl=US&ceid=US:en", "it": "hl=it&gl=IT&ceid=IT:it"}[lang]
    return "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:3d") + "&" + loc

T, W, O, R, G = "Testate", "Wildlife", "Organizzazioni", "Reddit/Community", "Regionali"
def S(name, url, auth, filt, cat, fb=None, meme=0, region=None):
    return dict(name=name, url=url, auth=auth, filt=filt, cat=cat, fb=fb, meme=meme, region=region)
FEEDS = [
 # Testate principali
 S("The Guardian Animals", "https://www.theguardian.com/world/animals/rss", 3, False, T),
 S("The Guardian Wildlife", "https://www.theguardian.com/environment/wildlife/rss", 3, False, T),
 S("BBC Science & Environment", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", 3, True, T),
 S("BBC wildlife/zoo (Google News)", None, 3, True, T, fb="site:bbc.co.uk OR site:bbc.com wildlife OR zoo OR \"marine life\" OR conservation"),
 S("National Geographic", None, 3, True, T, fb="site:nationalgeographic.com animals"),
 S("Smithsonian Animals", "https://www.smithsonianmag.com/rss/tag/animals/", 3, False, T),
 S("Smithsonian Science & Nature", "https://www.smithsonianmag.com/rss/science-nature/", 3, True, T),
 S("ScienceDaily Animals", "https://www.sciencedaily.com/rss/plants_animals/animals.xml", 2, False, T),
 S("Phys.org Plants & Animals", "https://phys.org/rss-feed/biology-news/plants-animals/", 2, False, T),
 S("Phys.org Ecology", "https://phys.org/rss-feed/biology-news/ecology/", 2, True, T),
 S("Live Science Animals", "https://www.livescience.com/feeds/tag/animals", 2, False, T),
 S("Popular Science Animals", "https://www.popsci.com/category/animals/feed/", 2, False, T),
 S("NYT Science", "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml", 3, True, T),
 S("Down To Earth (wildlife)", "https://www.downtoearth.org.in/rss/wildlife-biodiversity", 2, True, T, fb="site:downtoearth.org.in wildlife OR biodiversity OR animal", region="Asia"),
 S("The Japan Times (animali)", "https://www.japantimes.co.jp/tag/animals/feed/", 2, True, T, fb="site:japantimes.co.jp animal OR animals OR zoo OR bear", region="Asia"),
 S("Reuters", None, 3, True, T, fb="site:reuters.com animal OR zoo OR wildlife"),
 S("AP", None, 3, True, T, fb="site:apnews.com animal OR zoo OR wildlife"),
 S("ANSA", None, 2, True, T, fb=("site:ansa.it animali", "it"), region="Europa"),
 S("Google News: animali (EN)", None, 1, True, T, fb="animal OR zoo OR wildlife"),
 S("Google News: zoo nascite", None, 1, True, T, fb="zoo baby animal born"),
 S("Google News: viral animal", None, 1, True, T, fb="viral animal video", meme=8),
 S("Google News: rescue", None, 1, True, T, fb="animal rescued"),
 S("Google News: rare species", None, 1, True, T, fb="rare species spotted OR discovered"),
 S("Google News: animali (IT)", None, 1, True, T, fb=("animali", "it"), region="Europa"),
 S("Google News: zoo (IT)", None, 1, True, T, fb=("zoo cucciolo nato", "it"), region="Europa"),
 S("Google News: fauna selvatica (IT)", None, 1, True, T, fb=("fauna selvatica OR orso OR lupo", "it"), region="Europa"),
 # Testate dedicate wildlife / animali
 S("World Animal News", "https://worldanimalnews.com/feed", 2, False, W),
 S("The Animal Reader", "https://theanimalreader.com/feed/", 2, False, W, fb="site:theanimalreader.com"),
 S("The Dodo", "https://www.thedodo.com/feed", 1, False, W, fb="site:thedodo.com", meme=15),
 S("Mongabay", "https://news.mongabay.com/feed/", 3, True, W),
 S("Mongabay Animals", "https://news.mongabay.com/list/animals/feed", 3, False, W, fb="site:news.mongabay.com animals OR wildlife OR species"),
 S("Discover Wildlife", "https://www.discoverwildlife.com/feed", 2, False, W, fb="site:discoverwildlife.com"),
 S("Focusing on Wildlife", "https://focusingonwildlife.com/news/feed/", 1, False, W, fb="site:focusingonwildlife.com"),
 # Organizzazioni
 S("WWF (worldwildlife.org)", "https://www.worldwildlife.org/stories.rss", 2, False, O, fb="site:worldwildlife.org"),
 S("WWF Internazionale", None, 2, False, O, fb="site:wwf.org OR site:panda.org OR site:wwf.panda.org"),
 S("IUCN", "https://iucn.org/rss.xml", 2, False, O, fb="site:iucn.org"),
 S("WCS", "https://newsroom.wcs.org/rss", 2, False, O, fb="site:wcs.org"),
 S("ASPCA", "https://www.aspca.org/rss.xml", 2, True, O, fb="site:aspca.org"),
 S("PETA", "https://www.peta.org/feed/", 1, True, O, fb="site:peta.org"),
 S("World Animal Protection", None, 2, False, O, fb="site:worldanimalprotection.org OR \"World Animal Protection\""),
 S("AZA", "https://www.aza.org/rss", 2, False, O, fb="site:aza.org OR \"Association of Zoos and Aquariums\""),
 S("EAZA", None, 2, False, O, fb="site:eaza.net OR EAZA zoo", region="Europa"),
 # Community
 S("ZooChat", "https://www.zoochat.com/community/forums/-/index.rss", 1, True, R),
 # Regionali
 S("Regionale: Kenya", None, 1, True, G, fb="wildlife Kenya", region="Africa"),
 S("Regionale: Sudafrica", None, 1, True, G, fb="wildlife \"South Africa\"", region="Africa"),
 S("Regionale: Australia", None, 1, True, G, fb="Australia wildlife OR zoo", region="Oceania"),
 S("Regionale: India", None, 1, True, G, fb="India wildlife OR tiger OR elephant", region="Asia"),
 S("Regionale: Asia orientale", None, 1, True, G, fb="zoo OR wildlife China OR Japan OR Thailand", region="Asia"),
 S("Regionale: Europa zoo", None, 1, True, G, fb="Europe zoo OR \"zoo\" Germany OR France OR Spain OR UK", region="Europa"),
 S("Regionale: America Latina", None, 1, True, G, fb="wildlife Brazil OR Mexico OR Amazon", region="Americhe"),
]
SUBREDDITS = [("AnimalNews",0),("wildlife",0),("NatureIsFuckingLit",15),("natureismetal",15),("zoology",0),("ecology",0),("conservation",0),
 ("EndangeredSpecies",0),("zoos",0),("CaptiveWildlife",0),("AnimalsBeingBros",15),("aww",15),("marinebiology",0),("herpetology",0),("ornithology",0)]
REDDIT_UA = {"User-Agent": "linux:animal-news-dashboard:v1.1 (github.com/satorisync-byte/animal-news-dashboard)"}
REGION_RE = [("Africa", r"Kenya|South Africa|Sudafrica|Tanzania|Uganda|Botswana|Namibia|Zimbabwe|Congo|Nigeria|Ethiopia|Madagascar|Rwanda|Africa"),
 ("Asia", r"India|China|Cina|Japan|Giappone|Thailand|Indonesia|Borneo|Sumatra|Malaysia|Vietnam|Nepal|Sri Lanka|Philippines|Korea|Asia"),
 ("Oceania", r"Australia|New Zealand|Nuova Zelanda|Tasmania|Queensland|Papua"),
 ("Europa", r"\bUK\b|Britain|England|Scotland|Wales|Ireland|Italia|Italy|France|Francia|Germany|Germania|Spain|Spagna|Europe|Europa|Netherlands|Poland|Norway|Sweden|Trentino|Abruzzo"),
 ("Americhe", r"\bUS\b|U\.S\.|America|Canada|Mexico|Messico|Brazil|Brasile|Amazon|Florida|California|Texas|Alaska|Peru|Colombia|Argentina|Chile|Costa Rica|Yellowstone"),
 ("Antartide", r"Antarctic|Antartide")]
REGION_RE = [(n, re.compile(p)) for n, p in REGION_RE]
def find_region(text):
    for n, rx in REGION_RE:
        if rx.search(text): return n
    return None
AUTH_DOMAINS = {"reuters":3,"apnews":3,"bbc":3,"theguardian":3,"nytimes":3,"nationalgeographic":3,"cnn":3,"washingtonpost":3,
 "ansa":2,"corriere":2,"repubblica":2,"smithsonianmag":3,"phys.org":2,"sciencedaily":2,"mongabay":3,"livescience":2,"npr":3,"independent":2,"sky":2}

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
    """Prova il feed nativo; se vuoto/bloccato usa Google News site: come ripiego."""
    status = "nessun feed nativo"
    if feed["url"]:
        try:
            r = requests.get(feed["url"], headers=UA, timeout=20)
            d = feedparser.parse(r.content)
            if d.entries: return feed, feed["url"], r.status_code, "nativo", d.entries
            status = r.status_code
        except Exception as e:
            status = str(e)[:60]
    if feed["fb"]:
        u = gn(feed["fb"])
        try:
            r = requests.get(u, headers=UA, timeout=20)
            d = feedparser.parse(r.content)
            return feed, u, r.status_code, "Google News" + (f" (nativo: {status})" if feed["url"] else ""), d.entries
        except Exception as e:
            status = str(e)[:60]
    return feed, feed["url"], status, "fallito", []

def fetch_reddit():
    """Reddit: prima .json (punteggi/commenti), poi .rss; backoff su 429, interrompe se bloccato (es. IP dei runner CI)."""
    out, report, blocked = [], [], 0
    for sub, boost in SUBREDDITS:
        entries, status, mode = [], None, "fallito"
        if blocked >= 3:
            report.append((sub, boost, "saltato (Reddit blocca questo IP)", "fallito", [])); continue
        for kind in ("json", "rss"):
            url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit=25&raw_json=1" if kind == "json" else f"https://www.reddit.com/r/{sub}/top/.rss?t=day"
            for attempt in range(3):
                try:
                    r = requests.get(url, headers=REDDIT_UA, timeout=15); status = r.status_code
                except Exception as e:
                    status = str(e)[:40]; break
                if r.status_code == 429:
                    time.sleep(min(10, float(r.headers.get("Retry-After", 2 * (attempt + 1))))); continue
                break
            if status == 200:
                try:
                    if kind == "json":
                        for c in r.json()["data"]["children"]:
                            p = c["data"]
                            if p.get("stickied") or p.get("over_18"): continue
                            ext = p.get("url_overridden_by_dest") or ""
                            entries.append(dict(title=p.get("title", ""), summary=(p.get("selftext") or "")[:400], link="https://www.reddit.com" + p["permalink"],
                                ext=ext if ext and "reddit.com" not in ext and "redd.it" not in ext else "", ts=p.get("created_utc"),
                                score=p.get("score", 0), comments=p.get("num_comments", 0)))
                    else:
                        for e in feedparser.parse(r.content).entries:
                            m = re.search(r'href="([^"]+)">\[link\]', e.get("summary", ""))
                            ext = html.unescape(m.group(1)) if m else ""
                            entries.append(dict(title=e.get("title", ""), summary="", link=e.get("link", ""),
                                ext=ext if "reddit.com" not in ext and "redd.it" not in ext else "", ts=entry_time(e), score=None, comments=None))
                except Exception:
                    entries = []
                if entries: mode = "nativo (" + kind + ")"; break
            time.sleep(1.5)  # cortesia
        if not entries and status in (403, 429): blocked += 1
        report.append((sub, boost, status, mode, entries))
    return report

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
    with ThreadPoolExecutor(14) as ex:
        rfut = ex.submit(fetch_reddit)
        res = list(ex.map(fetch, FEEDS))
        rres = rfut.result()
    report, items = [], []
    def add(feed, title, summ, link, src, auth, t, **extra):
        text = title + " " + summ
        animal = find_animal(text)
        if feed["filt"] and not animal and not GENERIC.search(text): return False
        items.append(dict(title=title, summary=summ, link=link, source=src, feed=feed["name"], auth=auth, ts=t, animal=animal, text=text,
                          cat=feed["cat"], region=feed["region"] or find_region(text), meme_boost=feed["meme"], **extra))
        return True
    for feed, url, status, mode, entries in res:
        recent = 0
        for e in entries:
            t = entry_time(e)
            if not t or t < cutoff or t > now + 3600: continue
            title = clean(e.get("title")); summ = clean(e.get("summary"))[:400]
            src = feed["name"]; link = e.get("link", ""); auth = feed["auth"]
            if "news.google.com" in url:
                st = e.get("source", {}) or {}
                gsrc = st.get("title") or (title.rsplit(" - ", 1)[-1] if " - " in title else None)
                if " - " in title: title = title.rsplit(" - ", 1)[0]
                summ = ""  # sommari GN sono solo link
                href = (st.get("href") or "").lower()
                src = gsrc or src
                site_q = isinstance(feed["fb"], str) and feed["fb"].startswith("site:")
                auth = max([v for k, v in AUTH_DOMAINS.items() if k in href] + [feed["auth"] if site_q else 1])
            if add(feed, title, summ, link, src, auth, t): recent += 1
        report.append({"feed": feed["name"], "categoria": feed["cat"], "url": url, "modo": mode, "status": status,
                       "totali": len(entries), "recenti_rilevanti": recent, "ok": recent > 0,
                       "stato": "funzionante" if recent > 0 else ("vuoto" if entries or status == 200 else "fallito")})
    rfeed = dict(cat=R, region=None, filt=False, auth=1)
    for sub, boost, status, mode, entries in rres:
        recent = 0; f = dict(rfeed, name="r/" + sub, meme=boost)
        for e in entries:
            t = e["ts"]
            if not t or t < cutoff or t > now + 3600: continue
            if add(f, clean(e["title"]), clean(e["summary"])[:400], e["link"], "Reddit r/" + sub, 1, t,
                   ext=e["ext"], rscore=e["score"], rcomments=e["comments"]): recent += 1
        report.append({"feed": "r/" + sub, "categoria": R, "url": f"https://www.reddit.com/r/{sub}/", "modo": mode, "status": status,
                       "totali": len(entries), "recenti_rilevanti": recent, "ok": recent > 0,
                       "stato": "funzionante" if recent > 0 else ("vuoto" if entries or status == 200 else "fallito")})
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
        rs = sum(i.get("rscore") or 0 for i in its); rc = sum(i.get("rcomments") or 0 for i in its)
        vis = min(50, 14 * (n - 1) + (8 if n > 1 else 0) + (min(20, 4 * math.log10(1 + rs) + 2 * math.log10(1 + rc)) if rs or rc else 0)); authp = {1: 8, 2: 16, 3: 25}[maxauth]
        rec = max(0, 25 * (1 - age_h / HOURS))
        impact = round(min(100, vis + authp + rec))
        # Meme
        tags = [k for k, (rx, w) in KW_RE.items() if rx.search(text)]
        m = NAME_RE.search(text) or LEAD_NAME_RE.search(lead["title"]) or QUOTED_RE.search(lead["title"])
        named = m.group(1) if m else None
        if named and named.lower() in STOP | {"zoo", "the"}: named = None
        if named and "nome" not in tags: tags.append("nome")
        meme = sum(KW_RE[t][1] for t in tags if t in KW_RE) + (10 if named and "nome" in tags and not NAME_RE.search(text) else 0)
        meme += max(i["meme_boost"] for i in its)
        meme += 20 if animal in CUTE else (10 if animal else 0)
        if SAD_RE.search(lead["title"]): meme *= 0.5; tags.append("tragica")
        meme = round(min(100, meme))
        overall = round(0.45 * impact + 0.55 * meme)
        stories.append(dict(titolo=lead["title"], sommario=lead["summary"], link=lead["link"], fonte=lead["source"],
            fonti=srcs, n_fonti=n, altri_link=[{"fonte": i["source"], "link": i["link"]} for i in its[1:6]],
            data=datetime.fromtimestamp(lead["ts"], timezone.utc).isoformat(), ore_fa=round(age_h, 1),
            animal=animal, animale=ANIMALS[animal][0] if animal else "generico", named=named, tags=tags,
            impatto=impact, meme=meme, punteggio=overall,
            categoria=lead["cat"], categorie=sorted({i["cat"] for i in its}),
            regione=next((i["region"] for i in its if i["region"]), None) or find_region(text),
            link_esterno=next((i.get("ext") for i in its if i.get("ext")), None),
            reddit_score=rs if any(i.get("rscore") is not None for i in its) else None,
            reddit_commenti=rc if any(i.get("rcomments") is not None for i in its) else None))
    stories.sort(key=lambda s: -s["punteggio"])
    n_tot = len(stories); stories = stories[:400]  # limite per caricamento veloce
    for s in stories[:30]:
        s["token"] = make_token(s)
    with ThreadPoolExecutor(6) as ex:
        hits = list(ex.map(dex_check, [s["token"]["ticker"][1:] for s in stories[:30]]))
    for s, h in zip(stories[:30], hits):
        s["token"]["dex_solana"] = h  # None = controllo fallito
    out = {"generato": datetime.now(timezone.utc).isoformat(), "finestra_ore": HOURS, "feed": report, "storie_totali": n_tot, "storie": stories}
    json.dump(out, open("data.json", "w"), ensure_ascii=False, indent=1)
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html"), encoding="utf-8").read()
    open("index.html", "w", encoding="utf-8").write(tpl.replace("/*DATA*/null", json.dumps(out, ensure_ascii=False).replace("</", "<\\/")))
    ok = [r for r in report if r["ok"]]
    print(f"Feed funzionanti: {len(ok)}/{len(report)}")
    for r in report: print(("  OK " if r["ok"] else "  KO ") + f"[{r['categoria']}] {r['feed']}: {r['modo']} status={r['status']} tot={r['totali']} recenti={r['recenti_rilevanti']}")
    print(f"Storie: {len(stories)} -> index.html, data.json")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__))); main()
