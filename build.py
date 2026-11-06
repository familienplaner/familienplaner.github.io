# Baut familienplaner.github.io aus der bisherigen Familienboard-Version (familieadrian/planer)
# plus den Änderungen für mehrere Familien, eigene Adressen und die Admin-Liste.
import sys, re, json, hashlib, urllib.request
SRC = 'https://raw.githubusercontent.com/familieadrian/planer/main/'
EXPECT = sys.argv[1] if len(sys.argv) > 1 else ''
get = lambda f: urllib.request.urlopen(SRC + f).read().decode('utf-8')
s = get('index.html')
h = hashlib.sha256(s.encode('utf-8')).hexdigest()
if EXPECT and h != EXPECT: raise SystemExit('Ausgangsversion hat sich geändert: ' + h)
def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count: raise SystemExit('expected %d got %d for: %s' % (count, n, old[:90]))
    s = s.replace(old, new)
def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count: raise SystemExit('expected %d got %d for: %s' % (count, n, old[:80]))
    s = s.replace(old, new)

# --- Mitgliederliste: Standard nur für die ursprüngliche Familie
rep("""  const list = doc && Array.isArray(doc.list) && doc.list.some(m => !m.hidden) ? doc.list : DEFAULT_MEMBERS;""",
"""  const list = doc && Array.isArray(doc.list) && doc.list.some(m => !m.hidden) ? doc.list : fallbackMembers();""")
rep("""const MEMBERS = [], WHO = [], SCHOOL = [], byId = {};""",
"""const MEMBERS = [], WHO = [], SCHOOL = [], byId = {};
/* Aktuelle Familie (aus Supabase). Nur die ursprüngliche Familie startet mit den Standard-Personen. */
let FAMILY = null, FID = null;
const START_MEMBER = [{ id:'ich', name:'Ich', kid:false, color:'blau', short:'I' }];
const fallbackMembers = () => (DEMO || !FAMILY || FAMILY.legacy) ? DEFAULT_MEMBERS : START_MEMBER;""")
rep("""const memberList = () => { const d = mem_ && mem_.docs['config/members']; return d && Array.isArray(d.list) && d.list.some(m => !m.hidden) ? d.list : DEFAULT_MEMBERS; };""",
"""const memberList = () => { const d = mem_ && mem_.docs['config/members']; return d && Array.isArray(d.list) && d.list.some(m => !m.hidden) ? d.list : fallbackMembers(); };""")

# --- Laden/Speichern pro Familie
rep("""  const { data, error } = await sb.from('docs').select('path,data');
  if (error) throw error;""",
"""  const { data, error } = await sb.from('docs').select('path,data').eq('family_id', FID);
  if (error) throw error;""")
rep("""  if (!channel) channel = sb.channel('docs-live').on('postgres_changes', { event:'*', schema:'public', table:'docs' }, p => {
    if (p.eventType === 'DELETE') { if (p.old && p.old.path) delete mem.docs[p.old.path]; }
    else if (p.new && p.new.path) mem.docs[p.new.path] = p.new.data;
    memNotify();
  }).subscribe();""",
"""  if (!channel) channel = sb.channel('docs-live-' + FID)
    .on('postgres_changes', { event:'INSERT', schema:'public', table:'docs', filter:'family_id=eq.' + FID }, p => { if (p.new && p.new.path) { mem.docs[p.new.path] = p.new.data; memNotify(); } })
    .on('postgres_changes', { event:'UPDATE', schema:'public', table:'docs', filter:'family_id=eq.' + FID }, p => { if (p.new && p.new.path) { mem.docs[p.new.path] = p.new.data; memNotify(); } })
    .on('postgres_changes', { event:'DELETE', schema:'public', table:'docs' }, p => { if (p.old && p.old.path && p.old.family_id === FID) { delete mem.docs[p.old.path]; memNotify(); } })
    .subscribe();""")
rep("""    return sb.from('docs').upsert({ path: p, col: colOf(p), data, updated_at: new Date().toISOString() }).then(r => { if (r.error) dbErr(r.error); });""",
"""    return sb.from('docs').upsert({ family_id: FID, path: p, col: colOf(p), data, updated_at: new Date().toISOString() }, { onConflict: 'family_id,path' }).then(r => { if (r.error) dbErr(r.error); });""")
rep("""    return sb.from('docs').delete().eq('path', p).then(r => { if (r.error) dbErr(r.error); });""",
"""    return sb.from('docs').delete().eq('family_id', FID).eq('path', p).then(r => { if (r.error) dbErr(r.error); });""")

# --- Familien-Funktionen (nach dem Speicher-Block einfügen)
rep("""mem_ = mem;
/* ---------- Demo-Zugang""",
"""mem_ = mem;
/* ---------- Familie: gründen, beitreten, einladen ---------- */
const famErr = e => { const m = (e && (e.message || e.details)) || '';
  if (/code_unknown/.test(m)) return 'Diesen Einladungscode gibt es nicht. Bitte nochmal genau abtippen.';
  if (/already_member/.test(m)) return 'Dieser Zugang gehört schon zu einer Familie.';
  if (/name_missing/.test(m)) return 'Bitte einen Familiennamen eingeben.';
  if (/not_admin/.test(m)) return 'Nur wer die Familie gegründet hat, kann den Code ändern.';
  return 'Das hat nicht geklappt. Bitte Internet prüfen und nochmal versuchen.'; };
function setFamily(f){ FAMILY = f || null; FID = f ? f.id : null; membersSig = ''; window.dispatchEvent(new CustomEvent('fb-family')); }
async function loadFamily(){ const { data, error } = await sb.rpc('my_family'); if (error) throw error; setFamily(data || null); return FAMILY; }
async function createFamily(name, list){
  const { data, error } = await sb.rpc('create_family', { p_name: name }); if (error) throw error; setFamily(data);
  const r = await sb.from('docs').upsert({ family_id: FID, path: 'config/members', col: 'config', data: { list, updatedAt: Date.now() }, updated_at: new Date().toISOString() }, { onConflict: 'family_id,path' });
  if (r.error) throw r.error; return FAMILY; }
async function joinFamily(code){ const { data, error } = await sb.rpc('join_family', { p_code: code }); if (error) throw error; setFamily(data); return FAMILY; }
async function newFamilyCode(){ const { data, error } = await sb.rpc('new_family_code'); if (error) throw error; setFamily(data); return FAMILY; }
const inviteLink = () => location.origin + location.pathname + '?join=' + (FAMILY ? FAMILY.join_code : '');
const prettyCode = c => (c || '').replace(/^(.{4})(.{4})$/, '$1-$2');
const joinFromUrl = () => { try { const c = new URLSearchParams(location.search).get('join'); if (c) { lsSet('fb-join', c); return c; } return lsGet('fb-join') || ''; } catch (e) { return ''; } };
async function signOut(){ try { await sb.auth.signOut(); } catch (e) {} try { lsSet('fb-me', null); } catch (e) {} location.replace(location.origin + location.pathname); }
/* ---------- Demo-Zugang""")

# --- Anmeldung: Registrieren + Passwort vergessen
old_login_start = s.index("function Login({ onDone, onDemo }){")
old_login_end = s.index("/* ---------- App ---------- */", old_login_start)
s = s[:old_login_start] + r'''function Login({ onDone, onDemo, recovery }){
  const invited = !!joinFromUrl();
  const [mode, setMode] = useState(recovery ? 'newpw' : invited ? 'signup' : 'login');
  const [dpw, setDpw] = useState(''); const [derr, setDerr] = useState(''); const [showDemo, setShowDemo] = useState(false);
  const goDemo = async () => { setDerr(''); if (await demoOk(dpw.trim())) onDemo(); else setDerr('Das Gast-Passwort stimmt nicht.'); };
  const [email, setEmail] = useState(''); const [pw, setPw] = useState(''); const [pw2, setPw2] = useState('');
  const [err, setErr] = useState(''); const [info, setInfo] = useState(''); const [busy, setBusy] = useState(false);
  const back = location.origin + location.pathname;
  const sw = m => { setMode(m); setErr(''); setInfo(''); };
  const go = async e => { e.preventDefault(); setErr(''); setInfo('');
    const mail = email.trim();
    if (mode !== 'newpw' && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(mail)) { setErr('Bitte eine gültige E-Mail-Adresse eingeben.'); return; }
    if ((mode === 'signup' || mode === 'newpw') && pw.length < 8) { setErr('Das Passwort braucht mindestens 8 Zeichen.'); return; }
    if ((mode === 'signup' || mode === 'newpw') && pw !== pw2) { setErr('Die beiden Passwörter sind nicht gleich.'); return; }
    setBusy(true);
    try {
      if (mode === 'login') {
        const { error } = await sb.auth.signInWithPassword({ email: mail, password: pw });
        if (error) setErr(/confirm/i.test(error.message) ? 'Bitte zuerst den Link in der Bestätigungs-Mail antippen.' : 'Anmeldung fehlgeschlagen. E-Mail und Passwort prüfen.'); else onDone();
      } else if (mode === 'signup') {
        const { data, error } = await sb.auth.signUp({ email: mail, password: pw, options: { emailRedirectTo: back } });
        if (error) setErr(/registered|exists/i.test(error.message) ? 'Mit dieser E-Mail gibt es schon einen Zugang. Bitte anmelden.' : /signups? not allowed|disabled/i.test(error.message) ? 'Registrieren ist gerade ausgeschaltet.' : 'Registrieren hat nicht geklappt: ' + error.message);
        else if (data && data.session) onDone();
        else setInfo('Fast geschafft: Wir haben dir eine E-Mail an ' + mail + ' geschickt. Tippe auf den Link darin, dann geht es hier weiter.');
      } else if (mode === 'reset') {
        const { error } = await sb.auth.resetPasswordForEmail(mail, { redirectTo: back });
        if (error) setErr('Das hat nicht geklappt. Bitte später nochmal versuchen.'); else setInfo('Wenn es zu ' + mail + ' einen Zugang gibt, kommt gleich eine E-Mail mit einem Link zum neuen Passwort.');
      } else if (mode === 'newpw') {
        const { error } = await sb.auth.updateUser({ password: pw });
        if (error) setErr('Das neue Passwort konnte nicht gespeichert werden. Bitte den Link aus der E-Mail nochmal öffnen.'); else { toast('Neues Passwort gespeichert'); onDone(); }
      }
    } catch (x) { setErr('Keine Verbindung. Bitte Internet prüfen.'); }
    setBusy(false); };
  const T = { login: ['Anmelden', 'Einmal anmelden – das Gerät bleibt danach angemeldet.'],
    signup: ['Zugang anlegen', invited ? 'Du wurdest in eine Familie eingeladen. Leg dir einen Zugang an, dann bist du gleich dabei.' : 'Leg einen Zugang an. Danach gründest du deine Familie oder trittst mit einem Code bei.'],
    reset: ['Passwort vergessen', 'Gib deine E-Mail ein. Du bekommst einen Link, mit dem du ein neues Passwort festlegst.'],
    newpw: ['Neues Passwort', 'Leg jetzt dein neues Passwort fest.'] }[mode];
  return html`<div style="min-height:100%;display:flex;align-items:center;justify-content:center;padding:24px max(16px,env(safe-area-inset-right,0px)) 24px max(16px,env(safe-area-inset-left,0px))">
    <form class="card" style="width:100%;max-width:420px;gap:14px" onSubmit=${go}>
      <div class="logo" style="margin:0"><${Icon} n="home" size=${28} sw=${2.2} /></div>
      <h1 style="font-size:26px">Familienboard</h1>
      ${mode === 'login' || mode === 'signup' ? html`<div class="seg" role="group" aria-label="Anmelden oder registrieren" style="align-self:stretch">
        <button type="button" style="flex:1;justify-content:center" aria-pressed=${mode === 'login'} onClick=${() => sw('login')}>Anmelden</button>
        <button type="button" style="flex:1;justify-content:center" aria-pressed=${mode === 'signup'} onClick=${() => sw('signup')}>Registrieren</button></div>`
        : html`<h2 style="font-size:20px">${T[0]}</h2>`}
      <div class="sub" style="font-size:15px">${T[1]}</div>
      ${mode !== 'newpw' ? html`<label class="field">E-Mail<input id="login-mail" type="email" autocomplete="username" value=${email} onInput=${e => setEmail(e.target.value)} /></label>` : null}
      ${mode !== 'reset' ? html`<label class="field">${mode === 'login' ? 'Passwort' : 'Passwort (mindestens 8 Zeichen)'}<input id="login-pw" type="password" autocomplete=${mode === 'login' ? 'current-password' : 'new-password'} value=${pw} onInput=${e => setPw(e.target.value)} /></label>` : null}
      ${mode === 'signup' || mode === 'newpw' ? html`<label class="field">Passwort wiederholen<input id="login-pw2" type="password" autocomplete="new-password" value=${pw2} onInput=${e => setPw2(e.target.value)} /></label>` : null}
      ${err ? html`<div class="hint warn" role="alert">${err}</div>` : null}
      ${info ? html`<div class="hint" role="status">${info}</div>` : null}
      <button class="btn" type="submit" disabled=${busy}>${busy ? 'Einen Moment …' : { login: 'Anmelden', signup: 'Zugang anlegen', reset: 'Link schicken', newpw: 'Passwort speichern' }[mode]}</button>
      ${mode === 'login' ? html`<button type="button" class="btn ghost" style="border:0;min-height:40px" onClick=${() => sw('reset')}>Passwort vergessen?</button>` : null}
      ${mode === 'reset' ? html`<button type="button" class="btn ghost" style="border:0;min-height:40px" onClick=${() => sw('login')}>Zurück zum Anmelden</button>` : null}
      ${mode === 'login' || mode === 'signup' ? html`<div style="border-top:2px solid var(--line);padding-top:12px;display:flex;flex-direction:column;gap:10px">
        ${showDemo ? html`<div class="sub" style="font-size:14px">Der Demo-Zugang zeigt das Board mit Beispieldaten. Man kann sich alles ansehen, aber nichts abhaken oder eintragen.</div>
          <label class="field">Gast-Passwort<input id="demo-pw" type="password" autocomplete="off" value=${dpw} onInput=${e => setDpw(e.target.value)}
            onKeyDown=${e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); goDemo(); } }} /></label>
          ${derr ? html`<div class="hint warn" role="alert">${derr}</div>` : null}
          <button type="button" class="btn soft" onClick=${goDemo}>Demo ansehen</button>`
        : html`<button type="button" class="btn ghost" onClick=${() => setShowDemo(true)}><${Icon} n="star" size=${18} />Demo-Zugang (nur ansehen)</button>`}
      </div>` : null}
    </form></div>`;
}

/* ---------- Neue Familie gründen oder beitreten (nach dem ersten Anmelden) ---------- */
function FamilyStart({ onDone }){
  const code0 = joinFromUrl();
  const [mode, setMode] = useState(code0 ? 'join' : 'pick');
  const [fname, setFname] = useState(''); const [code, setCode] = useState(prettyCode(code0.toUpperCase()));
  const [rows, setRows] = useState([{ name:'', role:'Papa', kid:false, school:false }, { name:'', role:'', kid:true, school:false }]);
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  const upRow = (i, k, v) => setRows(r => r.map((x, j) => j === i ? Object.assign({}, x, { [k]: v }) : x));
  const build = () => { const out = []; const cols = PALETTE.map(p => p[0]);
    rows.filter(r => r.name.trim()).forEach((r, i) => { const name = r.name.trim();
      const o = { id: slugId(name, out), name, kid: !!r.kid, color: cols[i % cols.length], short: name[0].toUpperCase() };
      if (out.some(x => x.short === o.short)) o.short = name.slice(0, 2);
      if (r.kid) { o.school = !!r.school; } else if (r.role.trim()) o.role = r.role.trim();
      out.push(o); });
    return out; };
  const create = async e => { e.preventDefault(); setErr('');
    const list = build();
    if (!fname.trim()) { setErr('Bitte einen Namen für die Familie eingeben, z. B. „Familie Müller“.'); return; }
    if (!list.length) { setErr('Bitte mindestens deinen eigenen Namen eintragen.'); return; }
    if (!list.some(m => !m.kid)) { setErr('Mindestens eine Person muss erwachsen sein.'); return; }
    if (new Set(list.map(m => m.name.toLowerCase())).size !== list.length) { setErr('Jeder Name darf nur einmal vorkommen.'); return; }
    setBusy(true); try { await createFamily(fname.trim(), list); lsSet('fb-join', null); onDone(); } catch (x) { console.error(x); setErr(famErr(x)); } setBusy(false); };
  const join = async e => { e.preventDefault(); setErr(''); if (code.replace(/[^A-Za-z0-9]/g, '').length < 8) { setErr('Der Code hat 8 Zeichen, z. B. ABCD-2345.'); return; }
    setBusy(true); try { await joinFamily(code); lsSet('fb-join', null); onDone(); } catch (x) { console.error(x); setErr(famErr(x)); } setBusy(false); };
  const wrap = inner => html`<div style="min-height:100%;display:flex;align-items:center;justify-content:center;padding:24px max(16px,env(safe-area-inset-right,0px)) 24px max(16px,env(safe-area-inset-left,0px))">
    <div class="card" style="width:100%;max-width:560px;gap:14px">${inner}</div></div>`;
  if (mode === 'pick') return wrap(html`
    <div class="logo" style="margin:0"><${Icon} n="home" size=${28} sw=${2.2} /></div>
    <h1 style="font-size:26px">Willkommen!</h1>
    <div class="sub" style="font-size:15px">Gehört deine Familie schon zum Familienboard? Dann frag nach dem Einladungscode. Sonst gründest du eure Familie hier neu.</div>
    <button type="button" class="btn" onClick=${() => setMode('new')}><${Icon} n="plus" size=${20} />Neue Familie gründen</button>
    <button type="button" class="btn ghost" onClick=${() => setMode('join')}><${Icon} n="lock" size=${18} />Mit Einladungscode beitreten</button>
    <button type="button" class="btn ghost" style="border:0;min-height:40px" onClick=${signOut}>Abmelden</button>`);
  if (mode === 'join') return wrap(html`<form style="display:flex;flex-direction:column;gap:14px" onSubmit=${join}>
    <h1 style="font-size:24px">Familie beitreten</h1>
    <div class="sub" style="font-size:15px">Den Code findet jemand aus deiner Familie im Board unter „Familie verwalten“ → „Familie einladen“.</div>
    <label class="field">Einladungscode<input id="join-code" value=${code} onInput=${e => setCode(e.target.value.toUpperCase())} placeholder="ABCD-2345" autocomplete="off" autocapitalize="characters" style="font-size:22px;letter-spacing:2px;text-transform:uppercase" /></label>
    ${err ? html`<div class="hint warn" role="alert">${err}</div>` : null}
    <button class="btn" type="submit" disabled=${busy}>${busy ? 'Einen Moment …' : 'Beitreten'}</button>
    <button type="button" class="btn ghost" onClick=${() => { setErr(''); setMode('pick'); }}>Zurück</button></form>`);
  return wrap(html`<form style="display:flex;flex-direction:column;gap:14px" onSubmit=${create}>
    <h1 style="font-size:24px">Neue Familie gründen</h1>
    <label class="field">Name der Familie<input id="fam-name" value=${fname} onInput=${e => setFname(e.target.value)} placeholder="z. B. Familie Müller" autocomplete="off" /></label>
    <div class="field">Wer gehört dazu?<span class="sub" style="font-size:13px">Du zuerst. Weitere Personen, Farben und PINs kannst du später unter „Familie verwalten“ ändern.</span>
      <div class="list">${rows.map((r, i) => html`<div class="li" style="flex-wrap:wrap;gap:8px">
        <input class="input" style="flex:1 1 160px;height:44px" value=${r.name} onInput=${e => upRow(i, 'name', e.target.value)} placeholder=${i === 0 ? 'Dein Name' : 'Name'} aria-label=${'Name Person ' + (i + 1)} autocomplete="off" />
        <div class="seg" role="group" aria-label="Kind oder erwachsen"><button type="button" aria-pressed=${!r.kid} onClick=${() => upRow(i, 'kid', false)}>Erwachsen</button><button type="button" aria-pressed=${r.kid} onClick=${() => upRow(i, 'kid', true)}>Kind</button></div>
        ${r.kid ? html`<label class="row" style="gap:6px;font-weight:700"><input type="checkbox" checked=${r.school} onChange=${e => upRow(i, 'school', e.target.checked)} style="width:20px;height:20px" />Schule</label>`
          : html`<input class="input" style="flex:0 1 120px;height:44px" value=${r.role} onInput=${e => upRow(i, 'role', e.target.value)} placeholder="Papa, Mama …" aria-label=${'Bezeichnung Person ' + (i + 1)} autocomplete="off" />`}
        ${rows.length > 1 && i > 0 ? html`<button type="button" class="iconbtn" aria-label="Person entfernen" onClick=${() => setRows(rows.filter((x, j) => j !== i))}><${Icon} n="x" size=${18} /></button>` : null}
      </div>`)}</div>
      <button type="button" class="btn ghost small" onClick=${() => setRows(rows.concat([{ name:'', role:'', kid:true, school:false }]))}><${Icon} n="plus" size=${16} />Weitere Person</button></div>
    ${err ? html`<div class="hint warn" role="alert">${err}</div>` : null}
    <button class="btn" type="submit" disabled=${busy}>${busy ? 'Wird angelegt …' : 'Familie gründen'}</button>
    <button type="button" class="btn ghost" onClick=${() => { setErr(''); setMode('pick'); }}>Zurück</button></form>`);
}

/* ---------- Familie einladen (im Bereich „Familie verwalten“) ---------- */
function InviteCard(){
  const [, force] = useState(0); const [busy, setBusy] = useState(false); const [conf, setConf] = useState(false);
  useEffect(() => { const h = () => force(x => x + 1); window.addEventListener('fb-family', h); return () => window.removeEventListener('fb-family', h); }, []);
  if (DEMO || !FAMILY) return null;
  const copy = async t => { try { await navigator.clipboard.writeText(t); toast('Kopiert'); } catch (e) { toast('Bitte den Text markieren und kopieren'); } };
  const renew = async () => { setBusy(true); try { await newFamilyCode(); toast('Neuer Code erstellt – der alte gilt nicht mehr'); } catch (x) { toast(famErr(x)); } setBusy(false); setConf(false); };
  return html`<div class="field">Familie einladen<span class="sub" style="font-size:13px">Wer zu „${FAMILY.name}“ gehören soll (z. B. Partner, Oma, ein weiteres Handy mit eigenem Zugang), registriert sich und gibt diesen Code ein.</span>
    <div class="li" style="flex-wrap:wrap;gap:10px"><div class="tx"><b style="font-size:24px;letter-spacing:3px;user-select:all">${prettyCode(FAMILY.join_code)}</b><span style="white-space:normal;user-select:all">${inviteLink()}</span></div>
      <div class="row" style="gap:6px"><button type="button" class="btn small" onClick=${() => copy(inviteLink())}>Link kopieren</button>
        <button type="button" class="btn small ghost" onClick=${() => copy(FAMILY.join_code)}>Code kopieren</button></div></div>
    ${FAMILY.role === 'admin' ? (conf ? html`<div class="hint warn">Neuer Code? Der alte Code und alte Einladungslinks funktionieren dann nicht mehr. Wer schon dabei ist, bleibt dabei.
        <div class="row" style="margin-top:8px"><button type="button" class="btn small" disabled=${busy} onClick=${renew}>Neuen Code erstellen</button><button type="button" class="btn small ghost" onClick=${() => setConf(false)}>Abbrechen</button></div></div>`
      : html`<button type="button" class="btn ghost small" style="align-self:flex-start" onClick=${() => setConf(true)}>Neuen Code erstellen</button>`) : null}
    <button type="button" class="btn ghost small" style="align-self:flex-start;color:var(--danger)" onClick=${signOut}>Auf diesem Gerät abmelden</button></div>`;
}

''' + s[old_login_end:]

# --- In „Familie verwalten“ die Einladung zeigen
rep("""    <div class="field">Geräte<span class="sub" style="font-size:13px">Wem ein Gerät gehört""",
"""    <${InviteCard} />
    <div class="field">Geräte<span class="sub" style="font-size:13px">Wem ein Gerät gehört""")

# --- App: Familie laden, Startseite für neue Zugänge, Passwort-Link
rep("""  const [setup, setSetup] = useState(false);
  useEffect(() => { if (!ready || DEMO) return;""",
"""  const [setup, setSetup] = useState(false);
  const [recovery, setRecovery] = useState(/type=recovery/.test(location.hash));
  useEffect(() => { if (!sb) return; const { data } = sb.auth.onAuthStateChange(ev => { if (ev === 'PASSWORD_RECOVERY') { setRecovery(true); setAuth('out'); } });
    return () => { try { data.subscription.unsubscribe(); } catch (e) {} }; }, []);
  useEffect(() => { if (!ready || DEMO) return;""")
rep("""  useEffect(() => { if (!sb) return; sb.auth.getSession().then(r => setAuth(r.data && r.data.session ? 'in' : 'out')); }, []);
  useEffect(() => { if (auth !== 'in') return; startSync().then(() => setReady(true)).catch(e => { console.error(e); setLoadErr('Die Daten konnten nicht geladen werden. Ist die Tabelle angelegt (Anleitung Schritt 2)?'); }); }, [auth]);""",
"""  useEffect(() => { if (!sb) return; sb.auth.getSession().then(r => setAuth(r.data && r.data.session && !/type=recovery/.test(location.hash) ? 'fam' : 'out')); }, []);
  useEffect(() => { if (auth !== 'fam') return;
    loadFamily().then(f => setAuth(f ? 'in' : 'nofam')).catch(e => { console.error(e); setLoadErr('Deine Familie konnte nicht geladen werden. Bitte Internet prüfen und die Seite neu laden.'); setAuth('nofam'); }); }, [auth]);
  useEffect(() => { if (auth !== 'in') return; try { if (location.search || location.hash.indexOf('access_token') >= 0) history.replaceState(null, '', location.pathname + (VIEWS.some(v => '#' + v.id === location.hash) ? location.hash : '')); } catch (e) {}
    startSync().then(() => setReady(true)).catch(e => { console.error(e); setLoadErr('Die Daten konnten nicht geladen werden. Bitte Internet prüfen und die Seite neu laden.'); }); }, [auth]);""")
rep("""  if (auth === 'wait') return html`<div class="loading" style="padding:24px">Familienboard wird geladen …</div>`;
  if (auth === 'out') return html`<${Login} onDone=${() => setAuth('in')} onDemo=${() => { startDemo(); setReady(true); setAuth('demo'); }} />`;""",
"""  if (auth === 'wait' || auth === 'fam') return html`<div class="loading" style="padding:24px">Familienboard wird geladen …</div>`;
  if (auth === 'out') return html`<${Login} recovery=${recovery} onDone=${() => { setRecovery(false); try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {} setAuth('fam'); }} onDemo=${() => { startDemo(); setReady(true); setAuth('demo'); }} />`;
  if (auth === 'nofam') return loadErr ? html`<div class="main"><div class="hint warn" role="alert">${loadErr}</div><button type="button" class="btn" onClick=${() => location.reload()}>Neu laden</button></div>` : html`<${FamilyStart} onDone=${() => setAuth('in')} />`;""")

# --- Version hochzählen, damit alle Geräte aktualisieren
import re
m = re.search(r"const APP_VER = '(\d+)'", s); v = int(m.group(1)) + 1
s = s.replace(m.group(0), "const APP_VER = '%d'" % v)

# --- Zusatz: Fehlermeldungen Bilderlesen, Bus-Hook, Demo-Passwort, Breite Admin
rep("  if (c === 'rate_limited') return", "  if (c === 'quota') return 'Für heute ist das Bilderlesen für eure Familie aufgebraucht. Morgen geht es wieder.';\n  if (c === 'no_family') return 'Dein Zugang gehört noch zu keiner Familie.';\n  if (c === 'rate_limited') return")
rep("const fallbackMembers = () => (DEMO || !FAMILY || FAMILY.legacy) ? DEFAULT_MEMBERS : START_MEMBER;", "const isDemo = () => { try { return DEMO; } catch (e) { return false; } };\nconst fallbackMembers = () => (isDemo() || !FAMILY || FAMILY.legacy) ? DEFAULT_MEMBERS : START_MEMBER;")
rep("  const tts = SCHOOL.map(m => useDoc('timetables/' + m.id));", "  const ttl = useCol('timetables'); /* ein fester Hook, egal wie viele Schulkinder */\n  const tts = SCHOOL.map(m => { const t = (ttl || []).find(x => x.id === m.id); return ttl === undefined ? undefined : (t || null); });")

# Adresse je Familie: Hilfsfunktionen
rep("""const inviteLink = () => location.origin + location.pathname + '?join=' + (FAMILY ? FAMILY.join_code : '');""",
"""/* Auf familienplaner.github.io hat jede Familie ihre eigene Adresse: /<familie> */
const SLUG_SITE = /(^|\\.)familienplaner\\.github\\.io$/.test(location.hostname);
const pathSlug = () => { if (!SLUG_SITE) return ''; try { return decodeURIComponent(location.pathname.split('/')[1] || '').toLowerCase(); } catch (e) { return ''; } };
const familyUrl = f => SLUG_SITE && f && f.slug ? location.origin + '/' + f.slug : location.origin + location.pathname;
function showFamilyPath(){ if (!SLUG_SITE || !FAMILY || !FAMILY.slug || pathSlug() === FAMILY.slug) return;
  try { history.replaceState(null, '', '/' + FAMILY.slug + location.search + location.hash); } catch (e) {} }
async function renameFamily(name){ const { data, error } = await sb.rpc('rename_family', { p_name: name }); if (error) throw error; setFamily(data); showFamilyPath(); return FAMILY; }
const inviteLink = () => familyUrl(FAMILY) + '?join=' + (FAMILY ? FAMILY.join_code : '');""")
rep("""function setFamily(f){ FAMILY = f || null; FID = f ? f.id : null; membersSig = ''; window.dispatchEvent(new CustomEvent('fb-family')); }""",
"""function setFamily(f){ FAMILY = f || null; FID = f ? f.id : null; membersSig = ''; try { if (f && f.name) document.title = f.name + ' · Familienboard'; } catch (e) {} window.dispatchEvent(new CustomEvent('fb-family')); }""")

# Anmeldeseite zeigt den Familiennamen der Adresse
rep("""  const invited = !!joinFromUrl();
  const [mode, setMode] = useState(recovery ? 'newpw' : invited ? 'signup' : 'login');""",
"""  const invited = !!joinFromUrl();
  const [mode, setMode] = useState(recovery ? 'newpw' : invited ? 'signup' : 'login');
  const [fam, setFam] = useState(null);
  useEffect(() => { const sl = pathSlug(); if (!sl || !sb) return;
    sb.rpc('family_by_slug', { p_slug: sl }).then(r => { const f = r && r.data; if (!f) return; setFam(f);
      if (f.slug && f.slug !== sl) { try { history.replaceState(null, '', '/' + f.slug + location.search + location.hash); } catch (e) {} } }).catch(() => {}); }, []);""")
rep("""      <h1 style="font-size:26px">Familienboard</h1>
      ${mode === 'login' || mode === 'signup' ? html`<div class="seg" role="group\"""",
"""      <h1 style="font-size:26px">${fam ? fam.name : 'Familienboard'}</h1>
      ${fam ? html`<div class="sub" style="font-size:14px;margin-top:-8px">Familienboard</div>` : null}
      ${mode === 'login' || mode === 'signup' ? html`<div class="seg" role="group\"""")

# Verwaltung: Name/Adresse ändern
rep("""  return html`<div class="field">Familie einladen<span class="sub" style="font-size:13px">""",
"""  return html`<${FamilyNameCard} /><div class="field">Familie einladen<span class="sub" style="font-size:13px">""")
rep("""/* ---------- Familie einladen (im Bereich „Familie verwalten“) ---------- */""",
"""/* ---------- Name und Adresse der Familie ---------- */
function FamilyNameCard(){
  const [nm, setNm] = useState(FAMILY ? FAMILY.name : ''); const [busy, setBusy] = useState(false);
  if (DEMO || !FAMILY) return null;
  const admin = FAMILY.role === 'admin';
  const save = async e => { e.preventDefault(); const n = nm.trim(); if (!n || n === FAMILY.name) return; setBusy(true);
    try { await renameFamily(n); toast(SLUG_SITE ? 'Gespeichert – neue Adresse: ' + familyUrl(FAMILY).replace(/^https?:\\/\\//, '') : 'Gespeichert'); } catch (x) { toast(famErr(x)); } setBusy(false); };
  return html`<form class="field" onSubmit=${save}>Name der Familie
    <span class="sub" style="font-size:13px">${SLUG_SITE ? html`Eure Adresse: <b style="user-select:all">${familyUrl(FAMILY).replace(/^https?:\\/\\//, '')}</b>. Ändert ihr den Namen, ändert sich die Adresse mit – alte Links leiten weiter.` : 'So heißt eure Familie im Board.'}</span>
    ${admin ? html`<div class="row" style="flex-wrap:nowrap"><input id="fam-rename" class="input" style="flex:1;min-width:0" value=${nm} onInput=${e => setNm(e.target.value)} autocomplete="off" />
      <button class="btn small" type="submit" disabled=${busy || !nm.trim() || nm.trim() === FAMILY.name}>Speichern</button></div>`
      : html`<b>${FAMILY.name}</b>`}</form>`;
}

/* ---------- Familie einladen (im Bereich „Familie verwalten“) ---------- */""")

# Nach dem Laden der Familie die eigene Adresse anzeigen
rep("""    loadFamily().then(f => setAuth(f ? 'in' : 'nofam'))""",
"""    loadFamily().then(f => { showFamilyPath(); setAuth(f ? 'in' : 'nofam'); })""")
rep("""history.replaceState(null, '', location.pathname + (VIEWS.some(v => '#' + v.id === location.hash) ? location.hash : '')); } catch (e) {}""",
"""history.replaceState(null, '', location.pathname + (VIEWS.some(v => '#' + v.id === location.hash) ? location.hash : '')); } catch (e) {} showFamilyPath();""")
# Nach dem Gründen/Beitreten ebenfalls
rep("""  if (auth === 'nofam') return loadErr ? html`<div class="main"><div class="hint warn" role="alert">${loadErr}</div><button type="button" class="btn" onClick=${() => location.reload()}>Neu laden</button></div>` : html`<${FamilyStart} onDone=${() => setAuth('in')} />`;""",
"""  if (auth === 'nofam') return loadErr ? html`<div class="main"><div class="hint warn" role="alert">${loadErr}</div><button type="button" class="btn" onClick=${() => location.reload()}>Neu laden</button></div>` : html`<${FamilyStart} onDone=${() => { showFamilyPath(); setAuth('in'); }} />`;""")

# Dateien absolut laden, damit /<familie> funktioniert
rep("""l.href = ok && v !== 'heute' ? 'manifest-' + v + '.webmanifest' : 'manifest.webmanifest';""",
"""l.href = '/' + (ok && v !== 'heute' ? 'manifest-' + v + '.webmanifest' : 'manifest.webmanifest');""")
rep('<link rel="icon" href="icon.svg" type="image/svg+xml">', '<link rel="icon" href="/icon.svg" type="image/svg+xml">')
rep('<link rel="apple-touch-icon" href="icon.svg">', '<link rel="apple-touch-icon" href="/icon.svg">')
rep("fetch('index.html?u=' + Date.now()", "fetch('/index.html?u=' + Date.now()")
rep("navigator.serviceWorker.register('sw.js')", "navigator.serviceWorker.register('/sw.js')")
m = re.search(r"const APP_VER = '(\d+)'", s); v = int(m.group(1)) + 1
s = s.replace(m.group(0), "const APP_VER = '%d'" % v)
rep("""function showFamilyPath(){ if (!SLUG_SITE""", """const isAdminView = () => pathSlug() === 'admin' || location.hash === '#admin';
function showFamilyPath(){ if (isAdminView()) return; if (!SLUG_SITE""")
rep("""/* ---------- Name und Adresse der Familie ---------- */""", r'''/* ---------- Admin: alle Familien ---------- */
function AdminFamilies(){
  const [rows, setRows] = useState(null); const [err, setErr] = useState(''); const [q, setQ] = useState('');
  const load = () => { setErr(''); sb.rpc('admin_families').then(r => { if (r.error) setErr(/not_app_admin/.test(r.error.message) ? 'Dieser Zugang hat keine Admin-Rechte.' : 'Die Liste konnte nicht geladen werden.'); else setRows(r.data || []); }).catch(() => setErr('Keine Verbindung.')); };
  useEffect(load, []);
  const dt = v => v ? new Date(v).toLocaleDateString('de-DE', { day:'2-digit', month:'2-digit', year:'numeric' }) : '–';
  const list = (rows || []).filter(f => !q.trim() || (f.name + ' ' + (f.slug || '') + ' ' + (f.emails || '')).toLowerCase().includes(q.trim().toLowerCase()));
  const sum = k => (rows || []).reduce((a, f) => a + (+f[k] || 0), 0);
  return html`<main class="main" style="max-width:1100px;margin:0 auto;width:100%">
    <div class="head"><div><h1>Alle Familien</h1><div class="sub">${rows ? rows.length + ' Familien · ' + sum('zugaenge') + ' Zugänge · ' + sum('bilder_30_tage') + ' gelesene Bilder in 30 Tagen' : 'Admin-Übersicht'}</div></div>
      <div class="row"><button type="button" class="btn small ghost" onClick=${load}>Aktualisieren</button>
        <a class="btn small" href=${FAMILY && FAMILY.slug && SLUG_SITE ? '/' + FAMILY.slug : location.pathname} onClick=${() => { if (location.hash === '#admin') { location.hash = ''; location.reload(); } }}>Zum eigenen Board</a>
        <button type="button" class="btn small ghost" onClick=${signOut}>Abmelden</button></div></div>
    ${err ? html`<div class="hint warn" role="alert">${err}</div>` : null}
    ${rows ? html`<input id="adm-search" class="input" placeholder="Suchen (Name, Adresse, E-Mail)" value=${q} onInput=${e => setQ(e.target.value)} />
      <div class="card" style="padding:0;overflow:hidden"><div class="ovx"><table style="width:100%;border-collapse:collapse;font-size:14px;min-width:760px">
        <thead><tr style="text-align:left;background:var(--surface-2)">${['Familie','Adresse','Zugänge','Einträge','Bilder (30 T.)','Zuletzt aktiv','Gegründet','Code'].map(h => html`<th style="padding:10px 12px;font-weight:800;color:var(--muted)">${h}</th>`)}</tr></thead>
        <tbody>${list.map(f => html`<tr style="border-top:1px solid var(--line)">
          <td style="padding:10px 12px"><b>${f.name}</b>${f.legacy ? html` <span class="count">eigene</span>` : null}<div class="sub" style="font-size:12px;overflow-wrap:anywhere">${f.emails || f.gegruendet_von || ''}</div></td>
          <td style="padding:10px 12px">${f.slug ? html`<a href=${'/' + f.slug} target="_blank" rel="noopener">/${f.slug}</a>` : '–'}</td>
          <td style="padding:10px 12px;font-variant-numeric:tabular-nums">${f.zugaenge}</td>
          <td style="padding:10px 12px;font-variant-numeric:tabular-nums">${f.eintraege}</td>
          <td style="padding:10px 12px;font-variant-numeric:tabular-nums">${f.bilder_30_tage}</td>
          <td style="padding:10px 12px">${dt(f.zuletzt_aktiv)}</td>
          <td style="padding:10px 12px">${dt(f.created_at)}</td>
          <td style="padding:10px 12px;font-family:ui-monospace,monospace;user-select:all">${prettyCode(f.join_code)}</td></tr>`)}
        </tbody></table></div></div>
      ${!list.length ? html`<div class="empty">Keine Familie gefunden.</div>` : null}` : err ? null : html`<div class="loading">Familien werden geladen …</div>`}
  </main>`;
}

/* ---------- Name und Adresse der Familie ---------- */''')
# Link zur Admin-Liste in „Familie verwalten“ (nur für Admins)
rep("""    <button type="button" class="btn ghost small" style="align-self:flex-start;color:var(--danger)" onClick=${signOut}>Auf diesem Gerät abmelden</button></div>`;""",
"""    ${appAdmin ? html`<a class="btn ghost small" style="align-self:flex-start" href=${SLUG_SITE ? '/admin' : '#admin'} onClick=${() => { if (!SLUG_SITE) setTimeout(() => location.reload(), 50); }}>Admin: alle Familien ansehen</a>` : null}
    <button type="button" class="btn ghost small" style="align-self:flex-start;color:var(--danger)" onClick=${signOut}>Auf diesem Gerät abmelden</button></div>`;""")
rep("""  const [, force] = useState(0); const [busy, setBusy] = useState(false); const [conf, setConf] = useState(false);""",
"""  const [, force] = useState(0); const [busy, setBusy] = useState(false); const [conf, setConf] = useState(false); const [appAdmin, setAppAdmin] = useState(false);
  useEffect(() => { if (!sb || DEMO) return; sb.rpc('is_app_admin').then(r => setAppAdmin(!!(r && r.data))).catch(() => {}); }, []);""")
# App: Admin-Ansicht
rep("""  const V = view === 'check' ? Check""", """  if (auth === 'in' && isAdminView()) return html`<${AdminFamilies} />`;
  const V = view === 'check' ? Check""")

rep('<main class="main" style="max-width:1100px;margin:0 auto;width:100%">', '<main class="main" style="max-width:1100px;margin:0 auto;width:100%;box-sizing:border-box">')
s = re.sub(r"const DEMO_HASH = '[0-9a-f]*'", "const DEMO_HASH = '" + hashlib.sha256(b'fb-demo:Familie2026').hexdigest() + "'", s)

open('index.html', 'w').write(s); open('404.html', 'w').write(s)
for f in ['manifest.webmanifest'] + ['manifest-%s.webmanifest' % v for v in ['kalender','schule','einkauf','essen','sterne']]:
    m = json.loads(get(f))
    m['start_url'] = m['start_url'].replace('./', '/'); m['scope'] = '/'
    for ic in m.get('icons', []): ic['src'] = '/' + ic['src'].lstrip('./')
    for sh in m.get('shortcuts', []):
        sh['url'] = sh['url'].replace('./', '/')
        for ic in sh.get('icons', []): ic['src'] = '/' + ic['src'].lstrip('./')
    json.dump(m, open(f, 'w'), ensure_ascii=False, indent=2)
for f in ['sw.js', 'icon.svg']: open(f, 'w').write(get(f))
print('fertig, Version', re.search(r"const APP_VER = '(\d+)'", s).group(1))
