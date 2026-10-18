# Design handoff — inventario accionable (F1–F11)

> Fuente: `design_handoff_riftbound_manager/` (zip "Rift Manager", prototipo HTML/React-vía-Babel, hifi).
> Este documento **inventaría** el handoff y lo cruza con las decisiones FINALES de `openspec/roadmap.md`
> (que prevalecen sobre el prototipo). No contiene código de aplicación.
>
> **Convención de referencias**: `archivo:línea` relativo a `design/` del handoff
> (p. ej. `app.jsx:130` = `design_handoff_riftbound_manager/design/app.jsx`, línea 130).
> **Fuente de verdad**: el código (`riftbound.css`, `*.jsx`) gana sobre el `README.md` del handoff cuando discrepan
> (ver §0.2: el README describe cosas que el código no hace).
> Los datos del prototipo (`data.js`, 425 cartas OGN, precios sintéticos) **no se importan** (roadmap §6).

---

## 0. Resumen ejecutivo

### 0.1 Lo que hay que saber antes de empezar

| # | Hallazgo | Impacto |
|---|---|---|
| 1 | El prototipo es **mono-set (OGN)**, con **textos bilingües incrustados en los componentes** (`es?'..':'..'` ≈ 280 veces) y **100 % cliente** (`localStorage`). No hay login/registro, admin, landing, deck público, estados de carga/error. | F1/F2/F10/F11 requieren diseño nuevo con los mismos tokens. |
| 2 | Sólo **112 claves** en `I18N` (`helpers.jsx:5-52`); Decks, Events y Account **no usan `I18N`**: llevan sus textos inline (`deck-editor.jsx` ≈57, `events.jsx` ≈91, `account.jsx` ≈131 ternarios). | F1 debe definir el catálogo ES/EN real y migrar ≈ 280 strings. |
| 3 | La **accesibilidad es casi nula**: 4 atributos ARIA en toda la app, `<label>` sin asociar, `<a>` sin `href`, sin `:focus-visible` en botones, sin focus trap, targets de 22 px (< 24 px WCAG 2.5.8). | F1 (primitivas) + F11 (auditoría). Ver §7. |
| 4 | **Densidad**: `--row-h` y `--radius-sm` están definidos pero **no se consumen** en el CSS (`riftbound.css:34,35`); la densidad sólo cambia `--gap`, `--pad` y (compact) `--radius`. | Decidir si F1 implementa altura de fila real. |
| 5 | **Acento**: el CSS tiene decenas de `rgba(46,198,230,…)` y `var(--cyan)` fijos; con acento naranja la UI queda **mezclada**. `'mixed'` existe en el panel de tweaks pero no está implementado (`app.jsx:72`, cae a cyan). | F1: introducir `--accent-rgb`/`color-mix` y eliminar cian fijo. |
| 6 | La **regla de copias/zonas del mazo vive duplicada** en `app.jsx:123-136` y `deck-editor.jsx:9-14`, y `deckIssues` (`deck-editor.jsx:66-72`) **no cuenta el taller** mientras `canAddName` (`app.jsx:131`) sí. | F5: una sola fuente en backend + casos de test compartidos. Cuidado con `Math.round` JS vs `round()` Python (§5.3). |
| 7 | El dominio real ya tiene **playset 1–3 + autoventa del sobrante** (`rbcol_playset`, `app/routes/domains/collection.py:400-572`), distinto del "Playset = qty ≥ 3" y `selling` booleano del prototipo (`collection.jsx:146`). | Decisión abierta (§10) antes de F3/F7. |
| 8 | El `CardArt` placeholder es `aspect-ratio:3/4` pero las imágenes reales son **352×492 (≈5:7)** (`riftbound.css:197` vs `helpers.jsx:136`) → salto de layout al cargar imagen. | F2: unificar a 352/492 y tamaños responsive. |
| 9 | **Sales** no tiene entrada en la navegación móvil (`app.jsx:24` `BOTNAV` = cards/collection/decks/events/stats); Dashboard sólo por la marca; Account por el avatar. | F1: añadir "Más" o rediseñar `BottomNav`. |
| 10 | El **desktop se limita a `--maxw:1280px`** centrado y `padding-bottom:110px` incluso sin bottom nav (`riftbound.css:36,136`). El usuario quiere más datos, no más ancho. | §3 propone breakpoint `2xl` (≥1600) y layouts de 2-3 columnas por pantalla. |

### 0.2 Divergencias README ↔ código (el README ya está resumido en el roadmap; usar estos valores)

| Tema | README dice | Código real | Referencia |
|---|---|---|---|
| Alto topbar | ~62 px | **64 px** (56 px ≤680) | `riftbound.css:87,431` |
| Padding contenedor | 20 px (14 móvil) | **22 px** (15 px ≤680) | `riftbound.css:81,428` |
| Grid cartas | `minmax(148px,1fr)`, hover −3 px | **`minmax(150px,1fr)`**, hover **−4 px** + `0 18px 40px -18px rgba(46,198,230,.5)` | `riftbound.css:217,220` |
| Overlay modal | `rgba(0,0,0,.6)` + blur 6 | **`rgba(3,14,19,.72)` + blur 8**; modal `min(960px,100%)`, radio **18 px** | `riftbound.css:261-265` |
| Bottom nav | fondo `--panel-3`, label 11 px | fondo **`--header`**, label **10.5 px** | `riftbound.css:390-394` |
| Anillo de foco | `0 0 0 2px color-mix(accent 45%)` en inputs **y botones** | Sólo `.input/.select:focus` con `0 0 0 3px rgba(46,198,230,.14)` (cian fijo, alfa 14 %). **Botones sin estilo de foco.** | `riftbound.css:149,507` |
| Duración ICS | 3 h por defecto | 3 h skirmish/nexus/presencial/online, **8 h regional/nacional**, fin capado a 23:xx | `events.jsx:98-99` |
| Add-event modal | incluye "enlace" | **No hay campo enlace**; sí plazas, inscripción (€), premio, país | `events.jsx:205-270` |
| Formatos evento | "1v1, 2HG…" | Sólo **`1v1` / `2v2`** | `events.jsx:233` |
| Decks workspace | 2 cols `1fr 340px` ≥1100 + panel derecho con donut/valor/acciones | Lista+editor **1fr 2fr ≥960**; el editor se parte en 2 columnas internas **≥1240**; **no hay** panel derecho, ni donut, ni "valor" en panel (el valor está en cabecera y en cada deck-card) | `riftbound.css:327-333`, `deck-editor.jsx:455-465` |
| Deck issues | incluye "banquillo > 8" | **No existe** esa regla en `deckIssues` (sólo bloquea al añadir) | `deck-editor.jsx:57-74` |
| Deck card (lista) | arte del campeón, contadores main/runas/banquillo | Nombre, pips, badge validez, valor, `main/40`, "leyenda · campeón" (texto). Sin arte ni contadores de runas/banquillo | `deck-editor.jsx:204-219` |
| Dashboard | 4 KPIs (valor, nº cartas, nº mazos, variación del mes) + gráfico 12 m con tooltips + "más valiosas" + accesos a Collection/Decks | KPIs: **valor+sparkline, cartas totales/únicas, % completado del set, listings**; **sin gráfico**; listas "top movers" y "ventas recientes"; botones a Collection y **Cards** | `sections-a.jsx:43-114` |
| Stats | incluye "valor por set" | **No existe** valor por set; hay completado por set (nº cartas) | `sections-b.jsx:117-128` |
| Account → Interfaz | densidad, vista colección, acento, intensidad, proveedor, moneda | Sólo **intensidad de fondo, vista por defecto, proveedor/moneda**. **Densidad y acento sólo existen en el panel de tweaks** (no portable) | `account.jsx:483-531` |
| Account en móvil | `select` | **Pestañas horizontales con scroll** (`.acc-nav` en fila) ≤960 | `riftbound.css:644-651` |
| Sidebar Account | ≥900 px | **≥961 px** | `riftbound.css:644` |
| Gráficos | grid horizontal `--line-2` + tooltips | `PriceChart` **sin ejes, sin grid, sin hover** | `helpers.jsx:215-235` |
| Tamaño mínimo texto | "nada por debajo de 11 px" | 9 px (`.vqty`), 10 px (`.varchip`, `.evt-mine-tag`), 10.5 px (varios) | `riftbound.css:373,379,714` |
| Copiado | 1400 ms | 1400 ms (`CopyBtn`) **y 1600 ms** (ExportModal) | `account.jsx:71`, `deck-editor.jsx:120` |
| Confirmación destructiva | "no existe" | Borrar mazo usa `window.confirm` (`deck-editor.jsx:468`); borrar cuenta tiene doble paso (`account.jsx:400-411`) | — |

---

## 1. Design tokens (exactos)

### 1.1 `:root` (`riftbound.css:6-41`)

| Token | Valor | Uso / nota |
|---|---|---|
| `--bg-0` | `#06222c` | fondo base `body`, `.app-bg`, borde de segmentos de donut/`r` del marcador de PriceChart |
| `--bg-1` | `#0a2e3a` | sólo en degradados de avatar (`riftbound.css:516,640`) |
| `--panel` | `rgba(13,58,73,0.66)` | `.panel` (con `backdrop-filter: blur(12px)`), `.stat`, `.cardtile`, `.deck-card` |
| `--panel-2` | `rgba(9,42,55,0.82)` | `.panel-solid`, `.tablewrap`, inicio del degradado del modal |
| `--panel-3` | `rgba(7,34,45,0.92)` | `table.rb thead th`, fin del degradado del modal |
| `--header` | `rgba(6,26,34,0.78)` | topbar y botnav (blur 16) |
| `--line` | `rgba(120,205,228,0.16)` | bordes |
| `--line-2` | `rgba(120,205,228,0.10)` | separadores sutiles |
| `--cyan` | `#2ec6e6` | acento primario por defecto, labels de `.field`, títulos `.dsec-title` |
| `--cyan-bright` | `#5fe0ff` | hover/foco, `.kw`, KPI principal |
| `--cyan-dim` | `#1c8aa6` | degradados, barras |
| `--orange` | `#e8862e` | CTA (`.btn-orange`) y acento alternativo |
| `--orange-bright` | `#ff9d3f` | hover CTA, KPI listings |
| `--red` | `#dc4a31` | destructivo/error, `.btn-logout` |
| `--green` | `#33b27b` | positivo, `.switch.on` |
| `--gold` | `#e0b94a` | foil/showcase, tokens `:rb_might:`/`:rb_exhaust:`, bookmark |
| `--text` | `#eaf7fb` | texto principal |
| `--muted` | `#a6c7d2` | texto secundario |
| `--muted-2` | `#6f96a3` | terciario/placeholder (contraste 4.26 sobre `--panel`, ver §7) |
| `--accent` | `var(--cyan)` | acento activo (se sobrescribe en runtime: cyan u orange) |
| `--accent-ink` | `#04222b` | texto sobre acento (naranja usa `#160d03`, `app.jsx:72`) |
| `--bg-image-opacity` | `0.22` | opacidad del mapa (en runtime la fija `app.jsx:76`) |
| `--radius` | `14px` | paneles (compact: 11) |
| `--radius-sm` | `9px` | **definido y no usado** |
| `--gap` | `20px` | separación entre bloques |
| `--pad` | `18px` | padding de panel |
| `--row-h` | `54px` | **definido y no usado** |
| `--maxw` | `1280px` | ancho del contenedor |
| `--font-ui` | `'Manrope',system-ui,sans-serif` | UI |
| `--font-display` | `'Space Grotesk','Manrope',sans-serif` | títulos, cifras |
| `--shadow` | `0 18px 50px -20px rgba(0,0,0,0.6)` | paneles y `.cardart` |
| `--shadow-pop` | `0 30px 80px -20px rgba(0,0,0,0.75)` | modal |

Variables definidas **en runtime / inline** (no en `:root`): `--bg-image-filter` (fallback en `riftbound.css:63`: `saturate(0.85) contrast(1.02)`; la setea `app.jsx:78`), `--c` (color por chip de dominio / tipo de evento), `--vc` (color de variante/printing), `--cc` (marca de cuenta conectada).

### 1.2 Variantes de densidad (`riftbound.css:42-43`, aplicadas con `data-density` en `<html>`; regular = sin atributo, `app.jsx:71`)

| Token | regular | `compact` | `comfy` |
|---|---|---|---|
| `--gap` | 20px | 13px | 26px |
| `--pad` | 18px | 13px | 24px |
| `--row-h` | 54px | 44px | 62px (no consumido) |
| `--radius` | 14px | 11px | 14px |
| `--radius-sm` | 9px | 9px | 9px (no consumido) |

Consumidores reales de `--gap`/`--pad`: `.cardgrid`, `.statgrid`, `.stat`, `.evt-toolbar`, `.evt-card`, `.acc-*`, `.mt`. **Default del prototipo** (`TWEAK_DEFAULTS`, `app.jsx:8-13`): `density:"compact"`, `collectionView:"grid"`, `accent:"orange"`, `bgIntensity:250` — **distinto** de los defaults CSS (regular/cyan/0.22). Decidir los defaults de producto en F1 (el README sugiere regular/cyan; los datos del diseño final se ven con compact+orange).

### 1.3 Sólo modo oscuro

No hay `prefers-color-scheme`, ni tema claro, ni `color-scheme: dark` (falta; los `<input type=date|time>`, `<select>` nativos, checkboxes y scrollbars de Firefox salen claros — `events.jsx:241-243`, `collection.jsx:139`). Recomendado: `:root{color-scheme:dark}`, `<meta name="theme-color" content="#06222c">` y `background_color/theme_color` del manifest PWA = `#06222c`. Scrollbar WebKit: 10×10, thumb `rgba(120,205,228,.18)` radio 20 (`riftbound.css:75-77`); `html{scrollbar-gutter:stable}`.

### 1.4 Fondo de app (`riftbound.css:57-71`) e intensidad (`app.jsx:74-79`, `account.jsx:486-487`)

Capa `.app-bg` `position:fixed; inset:0; z-index:-2`:
1. `::before` imagen `assets/new_rift.webp` (`inset:-2%`, `cover`, `center`, `opacity:var(--bg-image-opacity)`, `filter:var(--bg-image-filter,…)`).
2. `::after` con 3 capas: `radial-gradient(120% 90% at 50% -10%, rgba(46,198,230,.10), transparent 55%)`, `radial-gradient(140% 120% at 50% 110%, rgba(6,28,36,.85), rgba(6,28,36,.45) 40%, rgba(6,28,36,.92))`, `linear-gradient(180deg, rgba(6,30,40,.55), rgba(5,24,32,.78))`.

Fórmula (motor 0–500, slider de Account 0–100 % → `round(p/100*250)`):
`opacity=min(1, bi/100*0.55)`; `over=max(0,bi-180)/100`; `filter: saturate(0.85+over*0.5) contrast(1.02+over*0.28) brightness(1+over*0.18)`.

| Slider % | bi | opacity | saturate | contrast | brightness |
|---|---|---|---|---|---|
| 0 | 0 | 0 | 0.85 | 1.02 | 1.00 |
| 16 | 40 | 0.22 (= default CSS) | 0.85 | 1.02 | 1.00 |
| 50 | 125 | 0.688 | 0.85 | 1.02 | 1.00 |
| 73 | 182 | 1 | 0.86 | 1.03 | 1.00 |
| 100 | 250 (default tweak) | 1 | 1.20 | 1.22 | 1.13 |

Nota: por encima del ≈73 % sólo cambia el filtro. Persistir como entero 0–100 en BD (`prefs.bg_intensity`) y mantener el mapeo.

### 1.5 Tipografía

- Familias: **Manrope** (UI) y **Space Grotesk** (display/cifras). `-webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility`. Mono (`ui-monospace,Menlo,monospace`) sólo para export de mazo, API key y código 2FA.
- Pesos **realmente usados**: Manrope **400** (herencia), **600**, **700**, **800** (500 se carga en el `<link>` pero el CSS no lo usa); Space Grotesk **600** (nombre en `CardArt`) y **700**. → ver §8 para self-host.
- Escala usada (px): 9, 10, 10.5, 11, 11.5, 12, 12.5, 13, 13.5, 14, 14.5, 15, 16, 17, 18, 19, 20, 22, 25, 27, 28, 30, 32, 34, 42.

| Rol | Tamaño/peso | Detalle | Ref |
|---|---|---|---|
| `.page-title` | 32 / 700 display (25 ≤680) | `letter-spacing:-0.02em; line-height:1.05` | `riftbound.css:138,430` |
| `.page-sub` | 14.5 muted | | `:139` |
| `.eyebrow` | 11.5 / 800 uppercase `.18em` accent | opacidad .9 | `:140` |
| `.section-label` | 12 / 800 uppercase `.14em` `--muted-2` | | `:141` |
| `.field label`, `.lbl` | 12 / 700 uppercase `.06em` **cyan fijo** | no sigue el acento | `:145` |
| Cuerpo / `.btn` | 14 / 500-700 | `.btn.sm` 13 | `:118,120` |
| `.badge` | 11.5 / 800 `.03em` | `.pill` 12/700 | `:180-181` |
| `table.rb th` / `td` | 11 / 800 uppercase `.06em` · 13.5 | | `:230,232` |
| `.stat .k` / `.v` / `.d` | 12/700 uppercase · **30**/700 display · 13 | | `:246-248` |
| `.tiny` | 12 | | `:406` |
| `.acc-h` | 17 / 700 display | | `:487` |
| `.evt-name` | 19 / 700 display, `text-wrap:balance` | | `:691` |
| `.brand` | 20 / 700 display `-0.02em` | marca = recuadro 30×30 `◆` + "**Riftbound** Manager" | `:88-94` |
| `.nav a` | 14.5 / 600 | icono 17 | `:97-98` |
| `.botnav a` | 10.5 / 700 | icono 21 | `:394-395` |
| Títulos bajo 11 px | `.vqty` 9, `.varchip`/`.evt-mine-tag` 10, `.dsec-btn`/`.attr .k`/`.pb .k`/`.evt-kv .k`/`.evt-cap-top .k` 10.5 | incumple "nada < 11 px" | ver §7 |

### 1.6 Breakpoints realmente usados

| Valor | Tipo | Efecto | Ref |
|---|---|---|---|
| `max-width:1080px` | CSS | `.modal-body` pasa a `260px 1fr` | `riftbound.css:413` |
| `min-width:960px` | CSS **y JS** (`useMediaQuery`) | Decks: lista (1/3) junto al editor (2/3); <960 el editor se inserta **inline bajo el mazo seleccionado** | `:327`, `deck-editor.jsx:185,220` |
| `max-width:960px` | CSS | Account: layout 1 col, sidebar → pestañas horizontales con scroll | `:644` |
| `max-width:920px` | CSS | `.dist-grid` 1 col; `.addgrid` 2 col | `:416` |
| `min-width:1240px` | CSS **y JS** | Decks: el editor se parte en 2 columnas (`.ws-cols`) | `:331`, `deck-editor.jsx:354` |
| `max-width:860px` | CSS | oculta `.nav` y texto de logout; muestra `.botnav`; modal-body 1 col | `:420` |
| `max-width:680px` | CSS | contenedor 15 px, topbar 56, tabla→cards, `.filtgrid` 1 col, statgrid 2, cardgrid min 118, modal pantalla completa, account/eventos 1 col | `:427`, `:652`, `:731` |
| `max-width:420px` | CSS | statgrid 1 col, `.bar-row` 74/42 px | `:446` |

Contenedor: `max-width:1280px` (no es breakpoint). Los grids con `auto-fill/auto-fit` (`cardgrid 150px`, `statgrid 220px`, `evt-grid 330px`) generan columnas sin media query.

**Propuesta de escala F1** (mobile-first, mantiene los valores del prototipo): `sm 680`, `md 860` (cambio de navegación), `lg 960`, `xl 1240`, **`2xl 1600` (nuevo, para el aprovechamiento de escritorio)**; exponerlos como tokens TS (`breakpoints.ts`) y como `@custom-media`/variables para que CSS y `useMediaQuery` no diverjan (hoy 960/1240 están duplicados CSS+JS).

### 1.7 Capas z-index

| Capa | z-index | Ref |
|---|---|---|
| `.app-bg` | −2 | `riftbound.css:57` |
| Dropdown `CardPicker` (inline) | 30 | `sections-a.jsx:25` |
| `.topbar` (sticky) | 40 | `riftbound.css:84` |
| `.botnav` (fixed) | 50 | `riftbound.css:390` |
| `.modal-bg` | 80 | `riftbound.css:261` |
| `TweaksPanel` | (no portar) | — |

Hueco a definir en F1: toasts/diálogos de confirmación (> 80) y menús/popovers (30-39). El dropdown del picker dentro de un modal funciona porque `.modal-bg` crea su propio contexto.

### 1.8 Transiciones y animaciones

| Elemento | Valor | Ref |
|---|---|---|
| `.nav a`, `.btn`, `.input`, `.deck-card`, `.ws-x/.ws-move/.ws-wb` | `.15s` (easing por defecto `ease`) | `riftbound.css:97,119,147,335,344` |
| `.chip`, `table.rb tr`, `.varchip` | `.12s` | `:161,233,374` |
| `.switch`, `.cardtile` | `.18s` | `:174,218` |
| `.acc-nav-btn`, `.acc-cur-btn`, `.evt-subnav button`, `.evt-near`, `.evt-save` | `.14s` | `:474,629,663,677,688` |
| `@keyframes fade` (modal-bg) | `.18s ease` | `:262-263` |
| `@keyframes rise` (modal) | `.22s cubic-bezier(.2,.7,.3,1)`, `translateY(18px)+opacity` | `:265-266` |
| `.foil-tag` | gradiente `120deg #7fe3ff,#b48bff,#7fe3ff`, 200 % size, `foil 3s linear infinite` | `:183-185` |
| Hover carta | `translateY(-4px)`, borde accent, sombra cian | `:220` |
| Hover fila deck | borde accent | `:336,341` |

**No hay `prefers-reduced-motion`.** Añadir en F1 (anula `foil`, `rise`, `fade`, `translateY`).

### 1.9 Foco

Actual: `.input,.select{outline:none}`; `:focus` → `border-color:var(--accent)` + `box-shadow:0 0 0 3px rgba(46,198,230,.14)` (cian fijo; contraste del anillo ≪ 3:1); `.acc-prefix:has(.acc-prefix-url):focus-within` igual (`riftbound.css:149,507`). **Botones, chips, segmentos, links, filas clicables: sin estilo propio** (queda el outline del navegador). Objetivo F1: `:focus-visible{outline:2px solid var(--accent); outline-offset:2px}` global (+ README: `box-shadow 0 0 0 2px color-mix(in srgb,var(--accent) 45%,transparent)` para inputs), nunca `outline:none` sin sustituto.

### 1.10 Formas, bordes, sombras, blur

| Elemento | Valor |
|---|---|
| Radios | paneles `var(--radius)`; botones/inputs 10; `.btn.sm` 9; chips 999; badges 7; pips 6; modal 18; cardart 11; cardtile 13; switches 999; avatar 18 (sm 12) |
| Blur | topbar 16 · botnav 16 · `.panel` 12 · modal-bg 8 |
| Botones | `.btn` pad 10×16, 14/700; `.sm` 7×12; primary = accent + sombra `0 8px 22px -10px accent`; orange igual; ghost `rgba(120,205,228,.06)` + borde `--line`; danger `rgba(220,74,49,.16)` texto `#ff9277`, hover `--red`/blanco; disabled opacidad .45 |
| Inputs | alto **42** (`.searchbar .input` 44), fondo `rgba(5,26,34,.6)`, borde `--line`, radio 10; select con chevrón SVG embebido, `padding-right:30` |
| Alturas de control inline | tablas `price-input` 78×34, `cond-select/lang-select` 34 |

### 1.11 Colores semánticos usados **inline** (no son tokens; convertir a tokens en F1)

| Uso | Valor | Dónde |
|---|---|---|
| Positivo (up / ok) texto | `#5fe0a8` (`.up`, `.st-shipped`, `.acc-badge-ok`) | `riftbound.css:224,187,540` |
| Negativo (down) texto | `#ff8a72` (`.down`), `#ff9277` (danger/cancelled), `#ffb38f` (warn global) | `:224,128,189,493` |
| Aviso (gold) texto | `#ecd070` (`.st-pending`, issues de mazo) | `:188`, `deck-editor.jsx:451` |
| Fondos tintados | ok `rgba(51,178,123,.16-.18)`, warn `rgba(224,185,74,.16-.18)`, err `rgba(220,74,49,.10-.20)` | varios |
| Tinta sobre naranja | `#160d03` | `:124`, `app.jsx:72` |
| Chart up / down | PriceChart `#33b27b`/`#dc4a31`; Sparkline `#5fe0a8`/`#ff8a72` (distintos) | `helpers.jsx:210,224` |

### 1.12 Paletas de dominio, rareza, tipos de evento, estados

| Dominio | Color | Glifo |
|---|---|---|
| Fury | `#e7504a` | ▲ |
| Calm | `#33b27b` | ❈ |
| Mind | `#4f86e6` | ☾ |
| Body | `#e08a36` | ✦ |
| Chaos | `#a45cc8` | ✺ |
| Order | `#d8b84a` | ✶ |
| Colorless | `#8aa3ad` | ◇ |

Rarezas: Common `#9fb6bf` · Uncommon `#4fb6a5` · Rare `#4f86e6` · Epic `#a45cc8` · Showcase `#e0a93a` (`data.js` `META`, línea 5).
Tipos de carta: Legend, Champion, Unit, Spell, Gear, Battlefield, Rune. Condiciones: MT, NM, EX, GD, LP. Idiomas: English, Spanish, French, German, Japanese.
Tipos de evento (`events.jsx:8-16`): regional `#e8862e`, nacional `#dc4a31`, skirmish `#2ec6e6`, nexus `#a45cc8` (oficiales); presencial `#33b27b`, online `#6f96a3` (no oficiales). Estado de venta: shipped (verde), pending (gold), cancelled (rojo) (`riftbound.css:186-189`). Marcas de cuentas conectadas: Discord `#5865F2`, Google `#ea4335`, Metafy `#7b5cff`, Cardmarket `#0b4ea2` (`account.jsx:19-22`).

> **Riesgo glifos**: ▲ ❈ ☾ ✦ ✺ ✶ ◇ ⟳ ◆ ⚡ ⬢ ⇩ ⇧ ▦ ▾ ▸ dependen de la fuente del sistema (algunos caen a emoji o a "tofu" en Android/iOS). Sustituir por SVG en F1.

---

## 2. Componentes globales

Nomenclatura destino: `frontend/src/components/ui/*` (primitivas), `…/domain/*` (cartas/mazos), `…/charts/*`.
"Gap a11y" = carencia observada en el prototipo; todos se corrigen en la implementación (F1 salvo indicación).

### 2.1 Átomos y datos de dominio

| Prototipo (ref) | Props / API | Comportamiento y estados | Gaps a11y / notas | Destino React |
|---|---|---|---|---|
| `Icon` (`helpers.jsx:60-113`) | `name`, `size=18`, `cls` | SVG 24×24, `stroke currentColor`, `strokeWidth 1.7`, redondeado, clase `.ic`. **47 iconos**: `dashboard cards collection decks sales stats search filter image export trash plus minus globe logout menu close edit tag check star grid list arrow coin account shield key sliders mail link device copy gift card refresh lock camera eye eyeoff calendar pin users trophy clock ticket bookmark`. Sin uso: `minus menu edit ticket`. `calendar` es el icono de la sección Events. Hay que añadir `settings/more/bell/wishlist/shield-admin/warning/offline/install` según fases. | Decorativo sin `aria-hidden`; `arrow` se usa sin rotar para "Prev" (`sections-a.jsx:174`). | `<Icon name size />` + `icons.tsx` (portar paths tal cual para fidelidad; Lucide opcional mapeando nombres). Añadir `aria-hidden="true"` por defecto. |
| `DomainPips` (`helpers.jsx:117-122`) | `domains: string[]`, `size?` | Por dominio un `.dpip` (20×20, radio 6, `inset 0 0 0 1px rgba(255,255,255,.25)`), fondo = color de dominio, glifo blanco; `title=d`; desconocido → Colorless. `size` fuerza ancho/alto y `fontSize = size*0.55`. | Sólo `title`; contraste del glifo blanco 1.9–2.7:1 sobre Order/Colorless/Body/Calm; glifos tipográficos (§1.12). | `<DomainPips domains size />` con SVG, `role="img"`+`aria-label` ("Fury, Order"). Tinta oscura sobre colores claros. |
| `RarityDot` (`helpers.jsx:123`) | `rarity` | 9×9 círculo con color de rareza, `title`. | Sólo color + title. | `<RarityDot>`; acompañar de texto o `aria-label`. |
| `CardArt` (`helpers.jsx:133-160`) | `card`, `fontScale=1` (**no usado**; `fs` es código muerto) | **Con imagen** (`CARD_IMG[card.id]`, sólo 5): `aspect-ratio 352/492`, `img` `object-fit:fill`, `loading="lazy"`, `alt=name`, sin sombra. **Sin imagen**: placeholder procedural (ver §2.2). Depende de que el padre tenga `container-type:inline-size` (`font-size:min(11cqw,22px)`); **todos los call-sites lo añaden a mano** (`sections-a.jsx:183,205`, `collection.jsx:140,166,193`, …). | Sin `onError`/fallback, sin `srcset`/dimensiones; placeholder 3:4 ≠ 5:7; `alt` sólo con imagen. | `<CardImage card size="thumb\|tile\|full" />` que encapsula el contenedor, el `aspect-ratio 352/492`, `srcset`, `onError → CardArtPlaceholder`, `loading/decoding`. URL = `RbCard.image_src` (roadmap §6). |
| `shade(hex, amt)` (`helpers.jsx:161-165`) | `#rrggbb`, `amt` en % | Cada canal `clamp(v + amt*2.55, 0, 255)` → `rgb()`. | Sólo acepta hex de 6 dígitos. | util `shadeHex()`. |
| `money/money0/pct` (`helpers.jsx:55-57`) | `n:number\|null` | `money`: `toLocaleString(undefined,{min2,max2})+" €"`; `money0`: `"€"+Math.round().toLocaleString()` (prefijo, sin decimales); `pct`: `+`/signo + `toFixed(1)+"%"` (decimal siempre `.`). Null/NaN → `—`. | Usan el **locale del navegador**, no el idioma de la app (README muestra `€1.204,50`). `money0` y `money` ponen el símbolo en lados distintos. `pct(undefined)` revienta. | `format.ts`: `formatMoney(n, lang)` con `Intl.NumberFormat(lang==='es'?'es-ES':'en-GB',{style:'currency',currency:'EUR'})`, `formatPct`, `formatMoneyCompact`. Única moneda: EUR. |
| `renderAbility` / `renderInline` / `runeColor` (`helpers.jsx:168-201`) | `text:string\|null` | Ver gramática §2.3. Vacío → `—` muted. | Glifos `⟳ ◆` y `title` en inglés hardcoded ("exhaust", nombre de runa); sin texto accesible; el contenedor `.ability` no usa `white-space:pre-line` (los datos no traen `\n`). | `<AbilityText text />` + `parseAbility()` (función pura testeable, devuelve AST). |
| `CardPicker` (`sections-a.jsx:5-37`) | `value` (id), `onPick(id\|null)`, `placeholder`, `filter(card)`, `matchTags`, `label(card)` | Input con icono lupa; al escribir, `onPick(null)` y abre; filtra `RB_CARDS` por `name.includes(q)` **o** `c.num===q` **o** (si `matchTags`) tags; **máx. 30**; cierra con `mousedown` fuera; fila = pips + label + `#num · type`; al elegir limpia query. Si hay `value` muestra su label (escribir lo deselecciona). Sin resultados → no pinta nada (ni "sin resultados"). | No es combobox ARIA; sin teclado (↑↓ Enter Esc); `div onClick`; dropdown `z-index:30` inline. | `<CardCombobox>` con patrón ARIA 1.2 (`role=combobox/listbox/option`, `aria-activedescendant`), búsqueda **server-side** debounced (`GET /cards?q=&…` con `filter` como query params: tipo, set, dominios, tags, "solo base printing"), estados `loading/empty/error`, hasta 30 resultados + miniatura real. Usado en Collection (alta), Decks (legend, champion, main, battlefields). |
| `FilterChips` (`sections-a.jsx:40`) | — | Stub que devuelve `null` (código muerto). | — | No portar. |

### 2.2 `CardArt` placeholder — algoritmo exacto (`helpers.jsx:142-159`, `riftbound.css:197-214`)

Contenedor `.cardart`: `aspect-ratio:3/4; border-radius:11px; background:#0a2630; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08), var(--shadow); isolation:isolate`; `font-size:min(11cqw,22px)`.

1. `doms = card.domains.map(d => color(d) ?? Colorless)`.
2. Fondo (`.grad`, opacidad .92): si **≥2 dominios** → `linear-gradient(150deg, d0 0%, d0 42%, d1 58%, d1 100%)` (corte duro diagonal; sólo se usan los 2 primeros). Si 1 → `radial-gradient(120% 130% at 30% 12%, shade(d0,+38), shade(d0,-30))`.
3. Brillo: `radial-gradient(90% 60% at 50% 8%, rgba(255,255,255,.18), transparent 60%)`.
4. `.glyph`: glifo del primer dominio, `font-size:62%`, `opacity:.16`, `rotate(-8deg)`, abajo-derecha (`right:-8%; bottom:-6%`).
5. `.frame`: `inset 0 0 0 1.5px rgba(255,255,255,.14), inset 0 0 30px rgba(0,0,0,.35)`.
6. `.tline`: `card.type` en mayúsculas 62 %, arriba (`left:6%; top:6%; translateX(34%)`).
7. `.cost` (si `energy != null`): círculo `26 %` de ancho, `radial-gradient(circle at 35% 30%,#1a3a47,#06181f)`, anillo cian `rgba(95,224,255,.5)`, Space Grotesk 700.
8. `.might` (si `might != null`): cuadrado `min-width:24 %`, abajo-derecha, anillo `--gold`.
9. `.name`: abajo, `padding:30% 9% 8%`, Space Grotesk 600, degradado `transparent → rgba(2,12,16,.86)`.

### 2.3 Gramática de `renderAbility` (`helpers.jsx:168-201`) — todos los tipos de token

Parseo en **dos pasos**: (1) `text.split(/(\([^()]*\))/g)` → trozos entre paréntesis **no anidados** se envuelven en `.reminder` (italic, `--muted-2`) y se renderizan por dentro con el mismo paso 2; (2) `renderInline` con regex `/(:rb_[a-z0-9_]+:|\[[^\]]+\])/g`.

| Token (en datos) | Render | Observado en OGN |
|---|---|---|
| `[Keyword]` — cualquier cosa entre corchetes, incluido `[>]`, `[Assault 2]`, `[Level 16]` | `.kw`: pill `rgba(46,198,230,.16)`, texto `--cyan-bright`, 12/800, radio 6, **sin corchetes** | 32 formas distintas (Action 41, Reaction 38, Hidden 29, Ganking 22, Add 19, Accelerate 19, Tank 14, Deflect 14, Legion 13, Shield 11, Assault 10, Deathknell 10, `[>]` 10, Vision 7, Temporary 7, Mighty 6, Weaponmaster, Equip, Stun, Ambush, Backline, Quick-Draw, Buff, Level N…) |
| `:rb_energy_N:` (`N` dígitos) | `.tok.tok-e`: círculo 18 px con número, mismo degradado que `.cost` | `energy_0…6` (0:17, 1:48, 2:9, 3:2, 4:4, 5:2, 6:1) |
| `:rb_exhaust:` | `.tok.tok-x`: `⟳` dorado 13 px, `title="exhaust"` | 48 |
| `:rb_might:` | `.tok-m`: `◆` dorado | 151 |
| `:rb_rune_<color>:` con `<color>` ∈ `fury calm mind body chaos order` | `.tok-r`: punto 13 px del color del dominio, `title=<color>`; color desconocido → `#7aa` | fury 13, mind 11, calm 10, body 8, order 6, chaos 3 |
| `:rb_rune_rainbow:` | `.tok-r.tok-rainbow`: punto con `conic-gradient(#e7504a,#e08a36,#d8b84a,#33b27b,#4f86e6,#a45cc8,#e7504a)` | 60 |
| cualquier otro `:rb_xxx:` | `.kw` con el nombre sin `:` ni `rb_` (fallback) | ninguno hoy; hay que mapear `:rb_power:` si aparece |

Texto plano restante: `Fragment`. Datos: 391 cartas con habilidad, 34 vacías (runas/tokens/campos), máx. 295 caracteres, **sin saltos de línea, sin paréntesis anidados ni desbalanceados**, sólo `—` y `’` como no-ASCII. Port: testear `parseAbility()` con estas muestras; no asumir markup adicional.

### 2.4 Visualización

| Prototipo (ref) | Props | Comportamiento | Gaps | Destino |
|---|---|---|---|---|
| `Sparkline` (`helpers.jsx:204-214`) | `data:number[]`, `w=120`, `h=34`, `color?` | Polilínea SVG, trazo 1.8; y = `h-4-((v-min)/rng)*(h-8)`; color auto `#5fe0a8` si último ≥ primero, si no `#ff8a72`. Devuelve `null` si vacío. | `data.length===1` → división por 0 (NaN); ancho fijo en px; sin `role="img"`. | `<Sparkline>` responsive (`viewBox`+`width:100%`), guard de 1 punto, `aria-label` ("sube 4,2 % en 7 d"). |
| `PriceChart` (`helpers.jsx:215-235`) | `data:number[]`, `h=150` | `viewBox 560×h`, `preserveAspectRatio="none"` (se **deforma** el círculo y el trazo), padding 10, área con degradado `#pcg` (id fijo → **colisión** si hay dos gráficos en pantalla, p. ej. modal sobre Stats), trazo 2.2, punto final r=4 con borde `#06222c`; verde `#33b27b` si sube, rojo `#dc4a31` si no. | **Sin ejes, sin grid, sin tooltip/hover, sin eje de fechas** (el README promete tooltips y grid `--line-2`); etiquetas externas hardcoded ("14 wk →", min/max). | `<PriceChart series range onRangeChange />`: ejes con fechas reales, rejilla `--line-2`, crosshair+tooltip accesible por teclado, selector de rango (7 d / 30 d / 90 d / 1 a / todo), series low/avg7/avg7_foil, `useId` para gradiente, `vector-effect:non-scaling-stroke`. Datos reales de `rbcm_price` (roadmap F2). |
| `Donut` (`helpers.jsx:236-246`) | `segments:{value,color,label}[]`, `size=150` | Anillo con radio interior 62 %, borde `#06222c` 1.5, orden de entrada; `a=-π/2`. | **1 solo segmento no se dibuja** (arco con inicio = fin); sin valor central, tooltip ni `role="img"`. | `<Donut>` con caso de 100 % (dos semicírculos o `circle`), valor central, leyenda interactiva, `aria-label`+tabla alternativa. Usado en Stats (dominio, rareza) y deseado en Decks. |
| `Bars` + `Legend` (inline en `sections-b.jsx:90-99`) | `obj`, `colorFn` | `.bar-row` grid `96px 1fr 52px`, pista 14 px radio 7; ordenadas desc. | Sólo color-fill; ≤420 px: `74px 1fr 42px`. | `<BarList>`; `<ChartLegend>`. |
| `.prog` progress (`riftbound.css:251-252`) | `width%` | 9 px, `linear-gradient(90deg,cyan-dim,cyan)` + glow. | Sin `role="progressbar"`. | `<ProgressBar value max label>`. |
| `MiniCurve` (`deck-editor.jsx:143-150`) | `buckets:number[]`, `labels:string[]`, `color?` | Barras `max(3,(v/max)*60)px` dentro de contenedor 70 px; valor encima (vacío si 0), etiqueta debajo (`bottom:-18px`, requiere margen inferior). Curva de energía: buckets `0..7+` (8); de poder: `0..4+` (5) (`deck-editor.jsx:245-246`). | Sin texto alternativo; etiquetas superpuestas si el siguiente bloque no deja hueco. | `<MiniCurve>` (en F5; también en Stats/Dashboard para curva de colección). |
| `StatCard` (`.stat`, `riftbound.css:244-248`) | `k` (icono+label), `v`, `d`, extras (sparkline/prog) | Panel con label 12/700 uppercase, cifra 30 px display tabular, subtexto 13. Grid `auto-fit minmax(220px,1fr)`; ≤680 2 cols; ≤420 1 col. | — | `<StatCard>` (+ `delta`, `loading`, `href`). |

### 2.5 Controles de entrada

| Prototipo (ref) | Props / estados | Gaps a11y | Destino |
|---|---|---|---|
| `.stepper` (`riftbound.css:168-171`; `.sm` 160-163) | Botones `–`(U+2013)/`+`, valor `min-width:34` tabular-nums. Límites **duros** (Collection: mín 1; runas: 0..12−otros; deck: `+` deshabilitado si `combined>=3`). `.sm`: botones 22×22 (`:361`). Deshabilitado = opacidad del botón, **sin tooltip** del motivo. | `–`/`+` sin `aria-label`; 22 px < 24 px; sin entrada numérica; sin `aria-live` del valor. | `<Stepper value min max onChange disabledReason>` (`role="spinbutton"` o grupo con `aria-label`), tooltip/`aria-describedby` con el motivo (README pide tooltip en vez de no-op silencioso). |
| `.switch` (`riftbound.css:174-177`) | 42×24; on = `--green`. **Dos usos**: `<span class="switch" onClick>` suelto (`collection.jsx:89,147,177`) y `Switch` de Account (`account.jsx:61-67`) como `<button>` que envuelve el span. | El span no es focusable; ninguno tiene `role="switch"`/`aria-checked`. | `<Switch checked onChange label>` con `role="switch"`. |
| Segmentado `.seg` (`riftbound.css:402-404`) y `.lang-toggle` (`:104-107`) | Botones con `.on` (fondo accent, tinta accent-ink). Usos: Tabla/Grid (Cards, Collection), ES/EN, 1V1/2V2/Todos, bandas de jugadores, proveedor, vista por defecto. Estado = prop local. | Sin `role="radiogroup"/aria-pressed`. | `<SegmentedControl options value onChange ariaLabel>`. |
| Chips (`riftbound.css:158-165`, `TypeChips` `events.jsx:282-293`) | Filtros multi-selección; `.on-domain` usa `--c`; tipo → fondo accent; rareza → fondo del color de rareza con texto `#06222c`; evento → `color-mix(--c 24%)`. | Sin `aria-pressed`. Contraste del texto `#06222c` sobre Epic 3.88:1. | `<FilterChip pressed color>` / `<ChipGroup>`. |
| `.field`+`.input/.select` (`riftbound.css:144-155`) | Label arriba (cian uppercase 12 px) + control alto 42. | **`<label>` sin `htmlFor`/anidado en TODO el prototipo** (`collection.jsx:60-96`, `events.jsx:223-270`, `account.jsx:131-352`). | `<Field label hint error>` que genera `id` con `useId` y enlaza `aria-describedby`. |
| Input con prefijo (`acc-prefix`, `riftbound.css:500-511`) | Prefijo `@`, URL o icono; `:has()` + `:focus-within`. | — | `<PrefixedInput>`. |
| `PwInput` (`account.jsx:416-420`) | Ojo mostrar/ocultar. | Botón con `tabIndex={-1}` y sin `aria-label` (inalcanzable por teclado). | `<PasswordInput>` con toggle accesible y `autocomplete`. |
| Slider (`.acc-slider`, `riftbound.css:623-625`) | `<input type=range>` con `accent-color`, valor 16 px display. | — | `<Slider>`. |
| Toggle de moneda `.acc-cur-btn` | **No portar** (moneda única EUR). | — | — |
| Checkbox de fila (`collection.jsx:139`) | Nativo. | Sin etiqueta; falta "seleccionar todo"; **la selección no se limpia al cambiar filtros/página** (`collection.jsx:12,124`). | `<Checkbox>`; selección acotada a la vista o con contador explícito. |

### 2.6 Contenedores, overlays y feedback

| Prototipo (ref) | Comportamiento | Gaps | Destino |
|---|---|---|---|
| `.modal-bg` + `.modal` (`riftbound.css:261-288`) | Overlay `fixed`, scroll interno, padding 34/18; modal `min(960px,100%)`; ≤680 `padding:0`, `min-height:100vh`, radio `18 18 0 0` (pantalla completa). Variantes: **CardModal** (Esc, bloqueo de scroll, cierre por `mousedown` en fondo, `role=dialog aria-modal`, `aria-label="Close"` en ✕ — `card-modal.jsx:4-16,31`), **ImportModal / ExportModal** (cierre por `onClick` del fondo, **sin Esc, sin bloqueo de scroll, sin role**, cierre `×`, `deck-editor.jsx:96,123`), **AddEventModal** (mousedown en fondo, `autoFocus`, sin Esc, sin role, `events.jsx:213`). | Sin focus trap ni retorno de foco; cierre por `onClick` cierra al soltar fuera tras seleccionar texto; `100vh` (usar `dvh`); sin `aria-labelledby`. | **Una sola primitiva** `<Modal title size onClose>` (+ `<Sheet>` móvil, `<ConfirmDialog>`): focus trap, Esc, scroll lock, `aria-labelledby`, cierre sólo si mousedown y mouseup ocurren en el fondo, animaciones `fade/rise`, `100dvh`. |
| `CollapseSection` (`deck-editor.jsx:162-177`) | Props `title`(node) `extra`(node) `children` `collapsible=true` `defaultOpen=true`; cabecera con botón `aria-expanded` y caret `▾/▸`; Legend y Champion usan `collapsible={false}`. Desmonta el cuerpo al cerrar; el estado se pierde al cambiar de mazo (`key={deck.id}`). | Sin `aria-controls`/región. | `<CollapsibleSection>`; persistir abierto/cerrado por usuario (pref local). |
| `CopyBtn` (`account.jsx:69-74`) | `navigator.clipboard.writeText(text)` sin await; muestra "Copied" 1400 ms (label `[copy, copied]`). `ExportModal` reimplementa con 1600 ms (`deck-editor.jsx:119-120`). | Muestra éxito aunque falle (HTTP sin Clipboard API); sin `aria-live`. | `useCopyToClipboard()` + `<CopyButton>` con fallback `execCommand` y toast; HTTPS ya obligatorio. |
| Descarga Blob (`collection.jsx:43`, `deck-editor.jsx:121`, `events.jsx:122-125`) | `URL.createObjectURL` + `<a download>.click()`; sólo el de mazo y el de ICS revocan la URL. | CSV sin BOM, sin escapado. | `downloadFile(name, mime, data)` único. Para exports masivos usar endpoints del backend (CSV con BOM como ya hace `export_csv`, `collection.py:758`). |
| Estados vacíos (`.empty`, `riftbound.css:459-460`) | Caja con glifo grande (`◇ ⌕ ◷`) + texto. Único vacío "ilustrado": My calendar (`events.jsx:481-490`). | Catálogo vacío muestra `t.not_in_collection` (mensaje equivocado, `sections-a.jsx:221`). | `<EmptyState icon title hint action>`; añadir `<Skeleton>`, `<ErrorState onRetry>`, `<OfflineBanner>`, `<Toast>` (no existen en el prototipo). |
| Badges (`riftbound.css:180-189`) | `.badge` (radio 7), `.pill`, `.status-badge .st-*`, `.foil-tag` (animado), `.cobadge`/`.fmt-badge` (24 px alto), `TypeBadge` (`events.jsx:129-134`, color-mix 20 % + inset 45 %). | Contraste de tipos `nacional` 3.29 / `nexus` 3.21. | `<Badge tone>`; `<FoilTag>` respeta `prefers-reduced-motion`. |
| Paginación (`sections-a.jsx:171-177`, `collection.jsx:113-119`) | Botones Prev/Next + "Page X of Y"; sin saltar a página. | Icono de "Prev" apunta a la derecha. | `<Pagination>` (en desktop: tamaño de página 48/96/192; plantear scroll virtual). |
| Tabla `table.rb` (`riftbound.css:227-241`) | `min-width:920`, `thead th` sticky (`top:0`, **relativo al wrapper con overflow**, no al viewport), filas hover `rgba(120,205,228,.05)`, `td` 13.5 px. En ≤680 la tabla de Collection se oculta y se pinta una lista de cards. | Sin `scope`, `caption`, sort accesible; `Catalog` table se oculta ≤680 **sin alternativa** (`riftbound.css:433`, `sections-a.jsx:197`). | `<DataTable>` con `columns`, `renderCard` para móvil, header sticky bajo topbar (`top:64px`, wrapper sin overflow en desktop), `aria-sort`. |

### 2.7 Shell y navegación

| Prototipo (ref) | Detalle | Destino |
|---|---|---|
| `Topbar` (`app.jsx:224-250`) | Marca (`◆` en recuadro degradado 30×30 + "Riftbound Manager"), `nav` de 7 enlaces (icono 17 + label; activo = texto `--text` + subrayado accent `bottom:-12px` con glow), derecha: `lang-toggle` ES/EN, `acc-trigger` (avatar 30 + primer nombre, máx. 120 px; nombre oculto ≤680), `btn-logout` rojo (texto oculto ≤860). **Logout no hace nada** (`app.jsx:247`). | `AppShell/Topbar` + `useAuth().logout()` |
| `BottomNav` (`app.jsx:270-274`) | 5 ítems: cards, collection, decks, events, stats. Icono 21 + label 10.5; activo cian con `drop-shadow`. `padding-bottom:calc(6px + env(safe-area-inset-bottom))`. Faltan Dashboard, **Sales**, Account. | `BottomNav` con "Más" (Dashboard, Sales, Account, idioma, logout). |
| Enrutado | Estado `route` en `localStorage` (`app.jsx:47,63`); `go()` hace `scrollTo(top)` (`:82`). Los `<a>` no tienen `href`. | React Router: `/`, `/cards`, `/cards/:set/:id`, `/collection`, `/decks`, `/decks/:id`, `/events`, `/sales`, `/stats`, `/account/:section`, `/admin/*`; gestión de foco + `document.title` por ruta. |
| `AccountTrigger` / `Avatar` | Iniciales (primeras 2 palabras) o imagen; se calcula en 3 sitios (`app.jsx:244`, `account.jsx:88,546`). | `<Avatar user size>`. |
| `PageHead` | `eyebrow` (métrica contextual) + `h1.page-title` + `page-sub?` + acciones a la derecha; `flex-wrap`. | `<PageHeader eyebrow title subtitle actions>`. |
| `SCard` (`account.jsx:47-60`) | Panel con `h3.acc-h` (icono accent), `desc`, `extra`, `children`; variante `danger`. | `<SettingsCard>`. |
| Hooks | `LS` (`app.jsx:3-6`), `EVL` (`events.jsx:63-66`), `useMediaQuery` (`deck-editor.jsx:153-159`), `useTweaks` (no portar). | `useLocalStorage` (sólo preferencias efímeras), `useMediaQuery` ligado a `breakpoints.ts`. |
| **Solo diseño (NO portar)** | `tweaks-panel.jsx` completo. Opciones que **sí** son producto: **densidad** (`compact\|regular\|comfy`), **vista por defecto de colección** (`table\|grid`), **acento** (`cyan\|orange`; `mixed` no implementado), **intensidad de fondo** (0–500, expuesta 0–100 %). | Preferencias de interfaz en BD (F1). |

---

## 3. Pantallas

### 3.0 Principios para escritorio (petición explícita del usuario: usar el espacio, no estirar)

- **Contenedor**: mantener `--maxw:1280px` para pantallas de lectura/formulario (Account, modales), y añadir `--maxw-wide: 1760px` (o fluido con `padding-inline: clamp(16px,2vw,32px)`) para pantallas de datos (Dashboard, Cards, Collection, Decks, Events, Sales, Stats, Admin). Eliminar el `padding-bottom:110px` fuera de móvil (`riftbound.css:136`).
- **Escala de columnas** (propuesta): `<860` 1 col + bottom nav · `860–1239` 1-2 cols + topbar · `1240–1599` (`xl`) panel lateral de filtros / 2 cols · `≥1600` (`2xl`) 3 cols (filtros | contenido | panel de detalle/resumen).
- **Patrón recurrente**: *panel de filtros fijo a la izquierda* (sticky bajo la topbar, `top:64px+gap`) con facetas y contadores; *resumen/KPIs* arriba en una banda; *panel de contexto* a la derecha (detalle de la carta seleccionada o análisis del mazo).
- **Densidad por tipo de dato**: tablas con más columnas (precio compra, P/L, variación 7 d, set, rareza, tags) y grids con más columnas (hasta 8–10 a 1920), no tiles más grandes.
- **Datos reales nuevos** que el diseño no contempla y que aprovechan el espacio: `avg7`, `avg7_foil`, `low`, tendencia 7/30 d, precio de compra y P/L, estado de legalidad por modo (1v1/2v2), bans, mazos que usan la carta, faltantes por mazo, próximos eventos guardados, alertas de precio.

### 3.1 DTOs comunes (propuesta; base `/riftbound/api/v1`)

| DTO | Campos |
|---|---|
| `CardSummary` | `set_id`, `card_id`, `num`, `name`, `domains[]`, `type`, `type_raw` (Champion Unit, Signature Spell, Token Unit, Basic Rune…), `tags[]`, `energy`, `power`, `might`, `rarity`, `image_src`, `foilable` (false en Basic Rune y Tokens), `price{market, market_foil, low, low_foil, source: "avg7_foil\|avg7\|low_foil\|low", trend_7d_pct, trend_30d_pct}`, `bans{"1v1":bool,"2v2":bool}`, `owned_qty` (si autenticado) |
| `CardDetail` | `CardSummary` + `ability` (texto con tokens), `artist`, `printings[]` (misma `name`: `set_id,card_id,num,rarity,image_src,price`), `related[]` (por tag), `in_decks[]` (`deck_id,name,qty`), `ban_info[]` (`mode,since,reason?`) |
| `PricePoint` | `date` (ISO), `price`, `price_foil`, `low`, `low_foil` (de `rbcm_price`/snapshots, F2/F4) |
| `CollectionLine` | `id`, `card: CardSummary`, `foil`, `qty`, `condition`, `language`, `selling`, `sell_price`, `purchase_price` (nullable, F3), `playset` (ver §10-1), `updated_at`, `market_price` (cadena `avg7_foil→avg7→low_foil→low`), `pl_abs`, `pl_pct` |
| `DeckSummary` | `id`, `name`, `mode` (`1v1\|2v2`), `legend`, `champion`, `domains[]`, `counts{main,runes,battlefields,sideboard,workbench}`, `legal{ok, mode, issues[{code,params}]}`, `value`, `updated_at`, `public_slug?` |
| `Rules` | `{deck_main:39, deck_total:40, runes:12, battlefields:3, sideboard:10, copies_max:3, workbench_max:100, modes:["1v1","2v2"]}` (roadmap §3) |
| `EventDTO` | `id`, `type`, `format`, `name`, `starts_at` (ISO con TZ), `country`, `city`, `venue`, `organizer`, `capacity`, `registered`, `fee_eur`, `prize`, `url`, `source` (`scraped\|manual`), `visibility` (`public\|private`), `owner_id?`, `saved` |
| `Prefs` | `{lang, density, accent, bg_intensity, collection_view}` (F1) |

### 3.2 Shell: topbar, bottom nav, contenedor (`app.jsx:222-292`, `riftbound.css:79-114,390-397`)

| Aspecto | Detalle |
|---|---|
| Layout | ≥861: topbar sticky 64 px (marca · nav 7 · [ES/EN] [avatar+nombre] [Logout]). ≤860: nav oculta, bottom nav fija 5 ítems, logout sólo icono. ≤680: topbar 56, nombre de usuario oculto. Contenedor `1280` con padding 22 (15 ≤680); `.page` padding `30 0 110` (`20 0 96` ≤680). |
| Datos | `account.name/avatar`, `lang`, ruta activa. |
| Acciones | navegar; cambiar idioma; ir a cuenta; logout (sin efecto). |
| Estado local | `lang`, `route`, `modalId` (card modal global), tweaks. |
| API | `GET /me` (→ usuario + `Prefs` + `is_admin` + `totp_enabled`), `PATCH /me/prefs`, `POST /auth/logout`, `GET /meta` (reglas, sets, enumeraciones, versión de precios). |
| Desktop: más datos | Buscador global en topbar (CardCombobox → ficha), indicador "Precios actualizados dd/mm hh:mm" (F4), campana con alertas de precio/eventos (F4/F8), indicador offline/"solo lectura" (PWA), acceso a Admin si `is_admin`. Card modal accesible desde cualquier ruta (`/cards/:set/:id` como ruta modal). |
| Móvil | "Más" en bottom nav con Dashboard, Sales, Account, Admin, idioma, logout, "Instalar app". Safe-area superior en PWA standalone (hoy sólo inferior, `riftbound.css:392`). |

### 3.3 Dashboard (`sections-a.jsx:43-114`)

| Aspecto | Detalle |
|---|---|
| Layout | Cabecera (`eyebrow "OGN · Origins"`, título `overview`, sub `est_prices_note`, botones Collection/Cards). `statgrid` (auto-fit 220 px): **valor de colección** (cian-bright + `Sparkline` 200×38 de `VALUE_HISTORY`), **cartas totales** (+ únicas), **completado del set** (`unique/425`, barra), **listings** (nº + valor). Debajo grid **inline `1.2fr 1fr` (no responsive; no colapsa en móvil, `sections-a.jsx:80`)**: *Top movers* (5, por `\|change\|`: pips, nombre, sparkline 70×24, precio, % ) y *Ventas recientes* (4). |
| Acciones | clic en fila → CardModal; botones a Collection/Cards/Sales. |
| Estado local | ninguno (todo derivado del inventario). |
| Fuentes del prototipo | `inventory`, `RB.VALUE_HISTORY` (12 meses sintéticos), `RB.SALES`, `card.history/change` sintéticos. |
| API (F4) | `GET /dashboard` → `{ kpis:{ value, value_delta_30d_pct, cards_total, cards_unique, set_completion:[{set_id,name,owned,total}], decks:{count, legal_count}, listings:{count,value} }, value_history:[{date,value,cost?}] (12 m, snapshot diario por usuario), movers:{up[],down[]} (7d/30d, de cartas del usuario **y** globales), recent_sales[], watchlist_alerts[], next_events[] }`. Para gráfico: `GET /collection/value-history?range=12m`. |
| Desktop: más datos | A ≥1280: gráfico de valor 12 m (con hover) 2/3 + rail derecho 1/3 (alertas de precio, próximos eventos guardados, mazos y su legalidad por modo). A ≥1600: 3 columnas — KPIs + gráfico / movers (subidas/bajadas 7 d/30 d) + watchlist / actividad reciente (altas, ventas, importaciones) + completado por set con barras por set. Dashboard sin datos (usuario nuevo): estado vacío guiado (importar CSV / añadir primera carta). |
| Reconciliación README | README promete gráfico con tooltips + mazos + "más valiosas": **no está** en código; es lo que F4 debe construir. |

### 3.4 Catálogo de cartas (`sections-a.jsx:117-224`)

| Aspecto | Detalle |
|---|---|
| Layout | Panel de filtros (búsqueda `44 px` + chips de 7 dominios + 7 tipos + 5 rarezas separados por divisor) → toolbar (`Showing N cards`, Prev, `Page X of Y`, Next) → **grid** `repeat(auto-fill,minmax(150px,1fr))` (118 ≤680) o **tabla** (10 columnas: imagen, set, ID, nombre, dominio, tipo, rareza, owned, precio, Δ; **oculta ≤680 sin fallback**). Toggle Tabla/Grid en cabecera (estado local, no persistido, default grid). 48/página. |
| Datos | `CardArt`, precio market + `pct(change)` por tile, check si está en la colección. |
| Búsqueda | `name`, `num` exacto, `ability`, `tags` (substring, case-insensitive). Filtros: dominios (**OR**: alguna coincidencia), tipos y rarezas (OR). Resetea a página 0 al cambiar. **No hay orden** ni filtro por set/energía/might/tags. |
| Estado local | `q, doms[], types[], rar[], page, view`. |
| API (F2) | `GET /cards?q=&set[]=&domain[]=&type[]=&rarity[]=&tag[]=&energy_min=&energy_max=&might_min=&might_max=&power_min=&power_max=&owned=&banned_mode=&foil=&price_min=&price_max=&sort=&dir=&page=&per_page=` → `{items:CardSummary[], total, facets:{domain:{Fury:55…}, type:{…}, rarity:{…}, set:{…}, tag:[{tag,count}]}}`. Importante para offline: `GET /cards/snapshot?since=` (catálogo completo versionado para IndexedDB, F1/F2). |
| Desktop: más datos | ≥1240: **panel lateral sticky** (≈280 px) con facetas + contadores, rangos de energía/might/poder, selector de set (multi-set), tags con búsqueda, "solo mías / faltantes", "baneadas en 1v1/2v2", rango de precio; resultados con `per_page` 96/192 y grid de 6–10 columnas. Tiles con: badge de cantidad poseída (no sólo check), variación 7 d, punto de rareza, indicador de ban por modo, precio foil. Vista tabla con columnas extra: energía/poder/might, tags, precio foil, tendencia 7/30 d, owned, bans. A ≥1600: panel derecho con **vista previa de la carta seleccionada** (la ficha completa en modal sólo en móvil/tablet). Añadir **ordenación** (nombre, precio, variación, número, rareza). |
| Móvil | filtros en `Sheet` desplegable con chips; la tabla debe degradar a lista (hoy se oculta). |

### 3.5 Ficha de carta / Card modal (`card-modal.jsx`)

| Aspecto | Detalle |
|---|---|
| Layout | `modal-bg` + `modal` 960 px. Cabecera: eyebrow `SET · #num`, `RarityDot`+rareza, **badge "BANNED"** si `card.banned` (booleano único), `h2` 26 px, pips 22 px, `typeRaw`, tags. Cuerpo `grid 300px 1fr` (260 ≤1080; 1 col ≤860 con arte máx 230): **izquierda sticky**: arte (máx 300), bloque de precios `Low / Market (resaltado) / High` (3 cols, valor 22 px; 18 ≤680) y fila "Precio recomendado (est.)" = market + variación. **Derecha**: `attrgrid` 2 col (energy, power, might ◆, type, rarity, domain), habilidad (`renderAbility`), historial (`PriceChart` 14 puntos "14 wk", min/max), *Mi inventario*, *Relacionadas* (hasta 6 por **primer tag**). |
| Mi inventario | Sin líneas: "Aún no está en tu colección" + botón Añadir. Con líneas (`invline`): `qty×`, FOIL, condición, idioma; si `selling` → pill con precio, input de precio y "Quitar de venta"; si no → "Poner en venta" (precio = market × 1.05 si no había). Botón añadir línea nueva (NM, English, qty 1, no foil). |
| Estado local | Ninguno (props). Esc cierra; `body.overflow=hidden`. |
| API (F2) | `GET /cards/{set}/{id}` → `CardDetail`; `GET /cards/{set}/{id}/prices?range=14w\|90d\|1y\|all` → `PricePoint[]`; líneas de la colección: `GET /collection?set=&card=` ; `PATCH/POST /collection/{id}`; bans por modo dentro de `CardDetail.bans`. |
| Desktop: más datos | Modal ancho (≈1200) a 3 columnas: arte+precios / atributos+habilidad+relacionadas / gráfico con selector de rango + tabla de **printings** (otras versiones, rareza, precio, owned) + "Usada en mis mazos" + "Baneada en 1v1 / 2v2" con fecha/motivo + "Faltan N para playset" + enlace a Cardmarket (si hay URL). Navegación ←/→ entre cartas del listado actual. Gráfico real: `low/avg7/avg7_foil`. |
| Cambios obligatorios | Quitar `recommended (est.)`/`est`; sustituir `banned` por mapa por modo; etiqueta "14 wk" dinámica; precios `Low/Market/High` → `low / avg7 / avg7_foil` según datos reales de Cardmarket (no hay "high" garantizado: confirmar columnas en F2). |

### 3.6 Colección (`collection.jsx`)

| Aspecto | Detalle |
|---|---|
| Layout | (1) Cabecera `N cards · valor total` + toggle Tabla/Grid (prop `view` de tweaks → pref BD). (2) Panel filtros `grid 3 cols` (Set, Card ID, Card name) → `.filtgrid` 1 col ≤680; "Advanced" despliega `auto-fit 150px`: Domain, Type, Rarity, Foil, Selling. Botones Advanced/Clear. (3) Panel *Add to collection*: `1.1fr 1.6fr .7fr .9fr .9fr 1fr` (Set, Card (CardPicker), Foil switch, Quantity stepper, Selling, Sell price) → `1fr 1fr` ≤920; 2ª fila `1fr 1fr 1.4fr` (Condition, Language, botón naranja Add 42 px). (4) Toolbar: Sort (set/name/price/qty/updated/rarity) + asc/desc, Show 25/50/100, Export. (5) Línea "Showing a–b of n" + Prev/Page/Next. (6) Barra de selección (`n selected` + Delete). (7) **Tabla** (15 cols; `min-width:920`) / **cards móviles** (≤680) / **grid**. |
| Tabla | checkbox, miniatura 40×54, set (badge), ID (`num`), nombre+pips, foil (`FOIL` animado / "No"), qty (stepper, mín 1), **Playset** (✓ si qty ≥ 3), selling (switch), sell price (input 78 px, sólo si selling), condition (select), language (select), updated, market price, borrar. |
| Grid | tile 5:7 + badge `N×` (izq-arriba), `FOIL` (der-arriba), badge naranja de tag si `selling` (`bottom:30%`), pie: precio + condición. |
| Datos | línea de inventario × carta; valor total = Σ market × qty de las filas filtradas. |
| Acciones | filtrar, ordenar, paginar, alta (un clic = **línea nueva**, no suma: `add_hint`), editar inline (qty, selling+precio, condición, idioma), borrar (sin confirmar), borrado masivo, exportar CSV, abrir carta. |
| Reglas | Precio de venta por defecto = `market × 1.05` (`collection.jsx:36,147,177`, `card-modal.jsx:106`); al activar `selling` sin precio se rellena; qty mínima 1 con stepper (borrar con papelera); `updated` se pisa con fecha fija (`app.jsx:85`). |
| Estado local | `fSet,fId,fName,adv,fDom,fType,fRar,fFoil,fSell`, formulario `aSet…aLang`, `sort,dir,ps,page`, `sel:Set` (no se resetea). |
| API (F3) | `GET /collection?set=&card_id=&q=&domain=&type=&rarity=&foil=&selling=&condition=&language=&sort=&dir=&page=&per_page=` → `{items:CollectionLine[], total, totals:{lines,qty,unique,value,cost,pl}}`; `POST /collection`; `PATCH /collection/{id}`; `DELETE /collection/{id}`; `POST /collection/bulk {ids[], op:"delete\|set_selling\|set_condition\|set_language\|set_price", value}` (edición en bloque, F3); `GET /collection/export?format=rbapp\|cardmarket&…` (CSV con BOM, ver §5.7); `POST /collection/import/preview` + `/import/commit` (asistente multi-formato; hoy existe `import_csv` `set;id;foil;qty` y `export_csv` Cardmarket); `GET/POST/DELETE /wishlist`. |
| Desktop: más datos | ≥1240: panel de filtros lateral permanente (colapsable); *Add* como drawer/columna lateral; tabla con columnas extra: **precio de compra, P/L (€ y %), variación 7 d, rareza, tags, set**; franja de resumen (valor, coste, P/L, líneas, únicas, valor en venta, % foil). A ≥1600: panel derecho con la línea/carta seleccionada (histórico de precio, otras líneas de la misma carta, mazos que la usan). Edición en bloque (bulk bar) y selección "todas las filtradas". Vista grid con control de tamaño y 8–10 columnas. |
| Cambios obligatorios | `selling` booleano ≠ `rbcol_playset 1–3` (decisión §10-1); CSV propio del prototipo (`set,id,name,foil,qty,condition,language,selling,sellPrice,marketPrice`) **no es** el formato Cardmarket ya existente; `Playset` calculado vs persistido; multi-set (el select Set de alta ni siquiera filtra el picker, `aSet` sin uso). |

### 3.7 Mazos

#### 3.7.1 Lista + workspace (`deck-editor.jsx:179-472`, `riftbound.css:301-387`)

| Aspecto | Detalle |
|---|---|
| Layout | Cabecera: `N decks`, `Deck Manager`, botones **Exportar** (deshabilitado sin mazo), **Importar**, **Nuevo mazo** (naranja/primary). `deck-layout`: `<960` columna única — la lista y, **bajo el mazo seleccionado, el workspace inline**; `≥960` `1fr 2fr` (lista / workspace); `≥1240` el workspace se divide en 2 columnas internas. |
| Deck card (lista) | Nombre display 18, `DomainPips`, badge **verde "Legal deck"** o **ámbar "N issues"**, valor (`money`, cian-bright) y `main/40`, línea "★ leyenda · campeón". Seleccionado = borde accent + glow. |
| Workspace cabecera | Input de nombre (display 18/700, `patchDeck` en cada tecla), pips de dominio, badge validez + `main/40 · valor`, **lista de issues** (caja ámbar con "• …"). |
| Orden de secciones (1 col) | Legend, Chosen champion, Battlefields, Main deck, Sideboard, Runes, Curva de energía, Curva de poder, Workbench. En 2 cols: col A = Legend + Main deck; col B = Champion, Battlefields, Sideboard, Runes, Energía, Poder, Workbench (`deck-editor.jsx:455-465`). |
| Legend / Champion (`pickRow`) | Miniatura 30×40, nombre (leyenda se muestra como "Tag, Nombre"), pips, stats (`n⚡ · n⬢ · n◆ · tag`), **tira de variantes** (printings) si hay ≥2, botón ✕ para quitar; si vacío, `CardPicker` filtrado (`legendFilter`/`champFilter`). Campeón: sólo `type==='Champion'` que **comparta tag** con la leyenda; muestra "Solo campeones con tag X". Título "(cuenta para 40)". |
| Battlefields | 3 slots (miniatura/número, nombre, ✕ o picker); `bfFilter` excluye ya elegidos; `battlefields.filter(Boolean)` compacta huecos. |
| Main deck | `CardPicker` de añadir (`addFilter`), ayuda de filtrado por colores/tag; sub-secciones **Unidades (Unit+Champion) / Gear / Hechizos / Otros**, A→Z (`localeCompare`), cada una con contador; fila = miniatura 28×38, nombre, stats, **variant strip** (chips con nº de printing y `vqty` si hay copias de esa versión), pips, **stepper sm** (total del nombre), acciones: ⇩ mover al banquillo (deshabilitado si lleno), ▦ mover al taller, ✕ quitar nombre. |
| Sideboard / Workbench | Mismo `cardRow`; ⇧ mover al main; Workbench: `(distintos/100)`, sin ▦; vacíos con hint de qué botón usar. |
| Runes | Sólo para colores de la leyenda (una fila por color: punto de color, "Fury Rune", stepper 0..); `(n/12)`; botón **Auto** (deshabilitado sin leyenda). Sin leyenda: hint. |
| Curvas | `energyCurve` buckets 0..7+ (incluye campeón elegido; excluye Battlefield/Rune; cuenta por **printing base**), `powerCurve` 0..4+ (power sólo si no null). |
| Footer | "Borrar mazo" (`confirm()` nativo). |
| Estado local | `selId`, `importing`, `exporting`; en workspace `CollapseSection.open`. Decks en `localStorage` (`rb_decks_v2`). |
| API (F5) | `GET /rules`; `GET /decks`, `POST /decks`, `GET/PUT/PATCH/DELETE /decks/{id}` (formato v2: `{name, mode, legend, champion, main[{set_id,card_id,qty}], runes[], battlefields[], sideboard[], workbench[]}`); `GET /decks/{id}/validation?mode=` → `{legal, issues:[{code,params}]}` (o incluido en el GET); `POST /decks/import {text, source:"rbapp\|riftdecks\|piltover"}` → `{deck, warnings[{line,text,reason}]}`; `GET /decks/{id}/export?format=text\|riftdecks\|piltover`; `GET /decks/{id}/vs-collection` → `{missing:[{card,need,have}], cost_eur}`; `GET /decks/{id}/versions`, `GET /decks/{id}/diff?a=&b=`; `POST /decks/{id}/share` → `{slug}`, `GET /public/decks/{slug}` (solo lectura); `GET /decks/{id}/hand-simulator?seed=` o cálculo cliente con el seed. Migración de mazos existentes: script, no pantalla. |
| Desktop: más datos | ≥1240: lista / editor (como ahora). **≥1600: 3 columnas — lista (con arte de leyenda/campeón, contadores main/runas/banquillo, legalidad 1v1 y 2v2, valor) / editor (legend, champion, battlefields, main, sideboard, runes) / panel de análisis sticky**: curvas energía/poder, reparto por tipo y dominio (`Donut`), valor total (propio vs coste de completar con la colección), legalidad por modo con explicación de cada issue, faltantes (`vs-collection`), simulador de mano inicial, diff de versiones y enlace público. Es lo que el README describía como "panel derecho" y el código no implementa. Mostrar miniatura real por fila y previsualización al pasar el ratón. |
| Cambios obligatorios | Banquillo 10 (no 8); `mode` en mazo y baneos por **nombre** y modo con aviso "no legal en 2v2 porque X"; límites silenciosos → tooltip con motivo; `valid` calculado en servidor; tokens (`Token Unit/Gear`) no seleccionables; ids con prefijo de set dinámico. |

#### 3.7.2 Modales Import / Export (`deck-editor.jsx:92-140`)

| | Import | Export |
|---|---|---|
| Layout | modal `max 560`: título, ayuda ("Pega el mazo con encabezados … o sólo cantidad + nombre"), `textarea` mono 13 px alto 240 (placeholder = ejemplo con Vex), botones Cancelar / Importar (deshabilitado si vacío). | modal `max 520`: `pre.export-pre` (max-h 340), botones **Descargar .txt** y **Copiar** (→ "¡Copiado!" 1.6 s). |
| Lógica | `onImportDeck` (§5.2): crea **un mazo nuevo**, selecciona y cierra; no informa de líneas no resueltas. | `exportDeckText` (§5.4); nombre de fichero `name.replace(/[^\w\-]+/g,'_')+'.txt'`. |
| API (F5) | `POST /decks/import` con vista previa (warnings) antes de crear. | `GET /decks/{id}/export?format=`; formatos riftdecks/piltover (roadmap F5). |
| Mejora | Pestañas de formato, drag&drop de fichero, vista previa con resolución por línea (carta elegida/printing/errores). | Selector de formato; "Copiar enlace público". |

### 3.8 Eventos (`events.jsx`)

| Aspecto | Detalle |
|---|---|
| Layout | Cabecera (`OGN · Origins · Juego organizado`, título, sub). `evt-subnav` (3 pestañas con contador): **Próximos / Historial / Mi calendario** (persistida `rb_evt_tab`). ≤680 pestañas a ancho completo. |
| Próximos | `statgrid`: Próximos (n), Este mes, En mi calendario. Panel de filtros: botón **"Añadir evento manual"**, `TypeChips` (6 tipos), segmentado Formato (Todos/1V1/2V2), select País (países presentes), botón **"Cerca de mí · {ciudad}"** (filtra por `account.country`, desactiva el select). Contador. `evt-grid` `auto-fill minmax(330px,1fr)` (1 col ≤680), orden por fecha asc. |
| `EventCard` | Etiqueta "Mío" (manual), badges tipo/formato/país, botón bookmark (guardar), nombre display 19, líneas: fecha larga + **chip "Hoy / Mañana / en N días / en 2 semanas"** (≤14 d), hora + organizador, sede·ciudad·país (o Online), premio; pie: **barra de plazas** `reg/cap` (naranja si completo) + inscripción (`N €`/Gratis); acciones: **Google Calendar** (link) y Guardar/Guardado (o papelera si manual). |
| Historial | Panel filtros: tipos, formato, **jugadores mínimos** (Todos/8+/16+/32+/64+/128+), país, desde/hasta (`date`), Limpiar. **Tabla** `min-width:900` (sin versión móvil): fecha, evento (+ ciudad·sede), tipo, formato, país, jugadores, **ganador** (pips del mazo + nombre + mazo). Orden fecha desc. Sólo eventos semilla pasados (los manuales pasados no aparecen). |
| Mi calendario | Vacío ilustrado + CTA. Con datos: panel "Exportar a Google Calendar" (`.ics` de **todos** los guardados), eventos futuros agrupados por mes (`evt-month`), "Ya celebrados" (opacidad .78). |
| Add-event modal | Campos: nombre*, tipo (6), formato (1V1/2V2), fecha*, hora (def. 18:00), país (7 incl. Online), ciudad* (no Online), lugar/tienda, organizador, plazas (def. 24), inscripción €, premio. Valida: `name && date && (ONLINE // city)`. Defaults al guardar: sede "Por confirmar/TBD", org "Yo/Me", `reg:0`; id `m<ts>`; vuelve a Próximos. |
| Estado local | `tab, saved[], manual[], showAdd`; filtros por vista. `EVT_TODAY='2026-06-01'` fijo. |
| API (F8) | `GET /events?scope=upcoming\|past&type[]=&format=&country=&near=&from=&to=&min_players=&mine=`; `POST /events` (manual, `visibility: private\|public`); `PATCH/DELETE /events/{id}` (sólo dueño); `PUT/DELETE /events/{id}/save`; `GET /events/{id}.ics`, `GET /me/calendar.ics?ids=` y feed suscribible con token; `POST /events/{id}/result {placement, record, deck_id, notes}` (resultado + mazo jugado); `GET /events/stats` (rendimiento por mazo/tipo); recordatorios push (`POST /push/subscriptions`). Los eventos scrapeados son siempre `public` (roadmap). |
| Desktop: más datos | ≥1240: filtros en panel lateral + grid 2–3 columnas; **vista mes** (calendario) alternable con la lista; columna derecha con "Mi próximo evento" y recordatorios. Historial con columnas **mi resultado / mazo jugado** (F8) y KPIs de rendimiento (win-rate por mazo, mejores resultados). Mi calendario: mes en rejilla + lista. Indicador de privado/público y de origen (scraper/manual). |
| Cambios obligatorios | País "cerca de mí" requiere país/ciudad del perfil (hoy `ACC_COUNTRIES` ≠ `EVT_CO`); tipos de evento deben coincidir con lo que entrega el scraper; el history del prototipo es "ganador del torneo", F8 añade "mi resultado". |

### 3.9 Ventas (`sections-b.jsx:5-74`)

| Aspecto | Detalle |
|---|---|
| Layout | Cabecera `N active listings`. `statgrid` (4): **Revenue** (sólo `shipped`, verde, "N orders" — texto inglés fijo), **Items sold**, **Profit** (`Σ(price−cost)×qty` de shipped, + `avg margin %`), **Active listings** (valor `Σ sellPrice×qty` + nº). *Active listings*: lista de paneles (miniatura 44×58, nombre, pips · `qty× · cond · lang · FOIL`, precio de mercado, input de precio de venta (€), **"profit" = (sellPrice − market)×qty** en verde/rojo, botón *Stop selling*). *Sales history*: tabla `min-width:760` (imagen, nombre, qty, cost, price, profit, buyer, date, status badge). |
| Estado local | ninguno (`RB.SALES` constante; edición de precio vía `onUpdateLine` sobre inventario). |
| Gaps funcionales | No se pueden crear ventas ni descontar inventario (README gap 4). |
| API (F7) | `GET /sales/summary?range=`; `GET /sales/listings` (líneas con `selling`); `PATCH /collection/{id}` (precio); `POST /sales {line_id, qty, price, buyer?, date?, status}` (**descuenta inventario**); `PATCH/DELETE /sales/{id}`; `GET /sales?status=&from=&to=`; `GET /sales/export?format=cardmarket` (existe `export_csv` con `name,language,quantity,price`, QUOTE_ALL, BOM). |
| Reglas (roadmap F7) | **Margen real** si hay `purchase_price`; si no, **comparación con el mercado del día** (ya es lo que hace la columna "profit" de listings: `sections-b.jsx:41`). En el historial `cost` es obligatorio en el prototipo → pasar a opcional (mostrar "—" y usar la comparación con mercado del día guardada en la venta). |
| Desktop: más datos | Dos columnas: listings editables (tabla densa con precio, mercado, Δ%, margen, "marcar vendida") / historial; gráfico de ingresos/margen mensual; filtros por estado/fecha/comprador; totales por set; "precio recomendado" (avg7/low) y alerta cuando el mercado baja del precio puesto; exportación Cardmarket. |

### 3.10 Estadísticas (`sections-b.jsx:77-169`)

| Aspecto | Detalle |
|---|---|
| Layout | (1) Panel *Valor en 12 meses*: valor actual (30 px) + `pct` sobre el primer punto (**mezcla valor real con serie sintética**, `sections-b.jsx:111`) + `PriceChart` 170 px + etiquetas de mes cada 2. (2) *Completado del set*: barra por set de `RB.SETS` (incluye "PRX · soon"). (3) `dist-grid` 3 col (1 col ≤920): **Donut por dominio** (contando una carta multidominio en cada dominio), **barras por tipo**, **Donut por rareza**. (4) 2 col: *Más valiosas* (top 6 por market, con qty) y *Top movers* (6 de **todo el catálogo**, no de las poseídas). |
| Datos | todo derivado en cliente de inventario × catálogo. |
| API (F6) | `GET /stats/collection?scope=all\|set` → `{value_history[], by_domain[{domain,qty,value}], by_type[], by_rarity[], by_set[{set_id,owned,total,value,cost}], top_value[], top_pl[], movers[], foil_ratio, completion_by_rarity}`. |
| Desktop: más datos | ≥1240: 2×2 de gráficos + panel de valor a ancho completo; **dominio/rareza/tipo por *valor* además de por cantidad** (toggle), valor por set (README lo prometía), matriz *set × rareza* de completado, top por P/L, evolución del P/L, ratio foil, valor en venta. ≥1600: 4 columnas de distribuciones. |

### 3.11 Cuenta (`account.jsx`, `riftbound.css:462-656`)

Shell: `acc-layout` `264px 1fr`; sidebar sticky (`top:84px`) con identidad (avatar 42 + nombre + email principal) y 4 botones de subsección; ≤960: 1 col, sidebar estático sin identidad, nav en fila con scroll. Subsección = estado local `sub` (README pide `/account/:section`). Aviso global si hay borrado programado (`acc-global-warn`). Todo vive en `account` (localStorage, `rb_account_v1`).

| Subsección | Contenido del prototipo | Veredicto vs roadmap | API (F9) |
|---|---|---|---|
| **Profile** | Avatar (FileReader→dataURL, 80 px, "PNG/JPG máx 2 MB" no validado); nombre, `@usuario` (sin espacios), bio (240); país (15) y ciudad; **correos múltiples** con Verificar/Principal/Eliminar; **redes** (7, con prefijo de dominio); **cuentas conectadas** (Discord, Google, Metafy, Cardmarket, toggle falso); **invitaciones** (5/mes por email); **suscripción** (3 planes) y **métodos de pago** (alta de tarjeta). | **Mantener**: avatar (subida a servidor), nombre/usuario/bio, país/ciudad, redes. **Mantener con cambios**: conexiones sólo Discord/Google (OAuth real); email: un único correo opcional **sin verificación** (no hay servidor de correo). **Eliminar**: invitaciones, planes, pagos. | `GET/PATCH /me`; `POST /me/avatar` (multipart, límite 2 MB, recorte cuadrado) / `DELETE`; `GET /auth/oauth/{discord\|google}/start`, callback; `DELETE /me/connections/{provider}`. |
| **Security** | Cambio de contraseña (actual, nueva ≥ 8, repetir; mensajes inline); **2FA** (switch + QR falso + código `7H4K·2P9Q·LX31·8MRV` fijo); **dispositivos** (3 filas, "Este dispositivo", revocar); **borrar cuenta** (confirmación en 2 pasos, cuenta atrás de 10 días, banner global + cancelar). | **Mantener y hacer real**: TOTP (QR + secreto + verificación + códigos de recuperación), tabla de sesiones en servidor (ua, ip aproximada, último uso), cambio de contraseña. **Decidir**: borrado programado 10 d (§10-3). | `POST /me/password`; `POST /me/2fa/setup` → `{secret, otpauth_uri}`; `POST /me/2fa/enable {code}` → `{recovery_codes[]}`; `POST /me/2fa/disable {password\|code}`; `GET /me/sessions`; `DELETE /me/sessions/{id}`; `DELETE /me/sessions` (cerrar el resto); `POST /me/delete`, `POST /me/delete/cancel`. |
| **API** | Generar clave (`rb_live_`+40 hex, `crypto.getRandomValues`), mostrar/ocultar (máscara `slice(0,12)+•×20+slice(-4)`), copiar, regenerar, revocar. | **Mantener** (roadmap F9), sin vinculación a plan. Servidor genera, **guarda hash** y muestra la clave **una sola vez**. | `GET /me/api-key` (metadatos: prefijo, creada, último uso); `POST /me/api-key` (devuelve la clave una vez); `DELETE /me/api-key`. |
| **Interface** | Intensidad de fondo 0–100 %; vista por defecto (tabla/grid); **proveedor** (Cardmarket/Cardtrader/TCGplayer) y **moneda** (EUR/USD/GBP/JPY). | Mantener intensidad y vista por defecto; **añadir densidad, acento e idioma** (hoy sólo en tweaks/topbar); **ocultar proveedor/moneda** (roadmap). | `PATCH /me/prefs {lang, density, accent, bg_intensity, collection_view}`. |
| Desktop: más datos | Contenido a una columna de ≈ 900 px. A ≥1240: 2 columnas de tarjetas (Perfil: identidad+bio | país/redes/conexiones; Seguridad: contraseña+2FA | sesiones con ubicación/UA/último uso y "cerrar todas") y vista previa en vivo de densidad/acento/fondo en Interfaz. Pestañas de subsección como rutas. |

### 3.12 Pantallas **sin diseño** en el handoff (necesitan diseño nuevo con estos tokens)

| Pantalla | Fase | Notas |
|---|---|---|
| Login, registro (CAPTCHA simple, límite de intentos, mensaje de cuenta bloqueada), reto 2FA, recuperación (sin email → "contacta al admin"), botones Discord/Google | F1 / F9 | Mismo estilo `panel`+`field`; sin diseño actual. |
| Lista de deseos (wishlist) y seguimiento de precios con alertas push | F3 / F4 | Reutilizar tile/tabla de Collection. |
| Asistente de importación CSV (selección de formato, mapeo de columnas, vista previa, conflictos) | F3 | Modal/pantalla multipaso. |
| Mazo público (solo lectura), simulador de mano, diff de versiones, mazo vs colección | F5 | Layout de análisis del panel derecho. |
| Admin (sets, edición de cartas, carga Cardmarket, mappings, ignorados, usuarios, baneos por modo) | F10 | "Pensado para escritorio" (tablas densas, formularios, 2–3 columnas). |
| Landing `/`, botón "Instalar app", pantalla offline/solo lectura | F11 / F1 | Hoy `app/routes/landing.py` existe en Jinja. |
| Permisos de notificaciones push, centro de notificaciones | F4 / F8 | Tarjeta de preferencias en Account. |


### 3.13 Matriz de layout por breakpoint (prototipo → propuesta de escritorio)

Ancho útil del contenedor del prototipo = `min(100vw, 1280) − 44` (−30 ≤680). Los grids `auto-fill/auto-fit` generan columnas sin media query.

| Pantalla | ≤680 | 681–860 | 861–1239 | ≥1240 en el prototipo | Propuesta ≥1240 / ≥1600 |
|---|---|---|---|---|---|
| Shell | topbar 56, bottom nav, sin nombre de usuario | topbar 64, bottom nav, nav oculta | topbar con nav 7 ítems | igual (contenedor 1280) | + buscador global, indicador de precios, campana; contenedor ancho (`--maxw-wide`) |
| Dashboard | KPIs 2 col (1 col ≤420); grid inferior **2 col forzadas (bug R1)** | KPIs 2-3 col; grid inferior 2 col | KPIs 3-4 col | KPIs 4 col + 2 listas `1.2fr 1fr` | gráfico 12 m + rail; ≥1600 3 columnas |
| Cards | grid min 118; **tabla oculta** | grid min 150 | idem | grid ≈ 6-7 col; sin facetas | panel lateral de facetas + grid 8-10 col; ≥1600 vista previa a la derecha |
| Collection | filtros 1 col; alta 2 col; **cards en vez de tabla**; grid | filtros 3 col; alta 2 col (≤920); tabla `min-width 920` con scroll | alta 6 col; tabla con scroll hasta ≈960 | tabla 15 col / grid | panel de filtros lateral + tabla con P/L, compra, 7 d; ≥1600 panel de detalle |
| Card modal | pantalla completa, arte ≤230 | 1 col, arte ≤230 | 260 px + 1fr (≤1080) | 300 px + 1fr (960 máx) | modal ≈1200 a 3 col; ←/→ entre cartas |
| Decks | lista + workspace inline bajo la tarjeta | idem | `<960` apilado; `≥960` `1fr 2fr` | workspace en 2 columnas internas | ≥1600: lista / editor / análisis sticky |
| Events | 1 col; tabs a ancho completo; historial con scroll horizontal | grid auto-fill 330 (2 col) | 2-3 col | 3 col | filtros laterales + 2-3 col + vista mes; historial con "mi resultado" |
| Sales | KPIs 2 col; listings en wrap; tabla 760 con scroll | idem | idem | KPIs 4 col; 1 col de listings | 2 col: listings / historial + gráfico |
| Stats | 1 col (KPIs/donut apilados) | `dist-grid` 1 col (≤920) | 3 col (>920) | 3 col + listas 2 col | 2×2 + valor a ancho completo; ≥1600 4 col |
| Account | 1 col; nav horizontal con scroll; `acc-grid-2`/planes 1 col | 1 col; nav horizontal | ≤960: 1 col; ≥961: sidebar 264 + contenido | sidebar + contenido (≈ 900 px) | tarjetas en 2 columnas + vista previa de interfaz |


---

## 4. i18n

### 4.1 Estructura actual (`helpers.jsx:5-52`)

- Un objeto plano `I18N = { en:{…}, es:{…} }`; claves `snake_case`; **112 claves por idioma, idénticas en ambos** (sin faltantes). Se usa como `t = I18N[lang]` (`app.jsx:60`) y se pasa por **props** (`t`, `lang`), no por contexto. Sin plurales, sin interpolación (se compone concatenando: `{t.showing} {n} {t.cards_l}`, el orden de palabras es fijo), sin fallback.
- Idioma por defecto **`en`** (`app.jsx:46`), persistido en `localStorage rb_lang`; el conmutador está sólo en la topbar. `<html lang="en">` fijo (`Riftbound Manager.html:2`).
- Fechas con `toLocaleDateString('es-ES' | 'en-GB')` (`events.jsx:73-81`); números con `toLocaleString(undefined)` (locale del navegador, no el de la app).

### 4.2 Grupos de claves (112)

| Grupo | Nº | Claves |
|---|---|---|
| Navegación | 7 | `dashboard cards collection decks events sales stats` (se resuelven con `t[n.id]`, `app.jsx:231,272`) |
| Chrome | 3 | `logout profile search_cards` |
| Títulos de página | 5 | `my_collection card_catalog deck_builder sales_manager statistics` |
| Filtros | 11 | `set all_sets card_id card_name domain type rarity advanced apply clear search` |
| Alta en colección | 10 | `add_to_collection add_hint card foil quantity selling sell_price condition language add` |
| Genéricas | 10 | `yes no sort_by ascending descending show page of next prev` |
| Tablas/etiquetas | 12 | `image name playset last_updated price actions delete showing to cards_l grid table` |
| Ficha de carta | 16 | `energy might power tags ability market low high price_history my_inventory not_in_collection list_for_sale stop_selling edit_price recommended est` |
| Mazos | 10 | `legend champion main_deck validation valid_deck issues mana_curve deck_value select_deck domains_id` |
| Ventas | 11 | `active_listings sales_history revenue items_sold profit avg_margin buyer date status cost no_listings` |
| Dashboard/Stats | 17 | `coll_value value_over_time set_completion owned by_domain by_type by_rarity top_valuable top_movers total_cards unique listings overview quick recent_sales foil_only est_prices_note` |

Claves **definidas y nunca usadas** (13): `apply champion deck_value domains_id edit_price foil_only mana_curve profile quick search select_deck to validation`. Valores iguales en EN y ES (legítimos): `set foil no playset might power est foil_only`.
Textos a **eliminar** al portar: `est`, `recommended`, `est_prices_note` ("estimaciones según la rareza"), `edit_price` (sin uso).

### 4.3 Textos **fuera** de `I18N`

| Dónde | Mecanismo | Volumen |
|---|---|---|
| `deck-editor.jsx` (Decks, issues, modales, secciones) | ternario `es?'…':'…'` | ≈ 57 |
| `events.jsx` (todo Eventos, `EVT_TYPE`/`EVT_CO` con `{es,en}`, "Hoy/Mañana/en N días") | ternario y objetos `{es,en}` | ≈ 91 |
| `account.jsx` (todo Account, `ACC_PLANS` con `{name,tag,feats}{es,en}`) | ternario y objetos | ≈ 131 |
| `app.jsx` (nombres de mazo "Mazo nuevo/Mazo importado", tweaks, "Mi cuenta") | `lang==='es'?…` | ≈ 10 |
| Inglés sin traducción en ningún sitio | literales | `collection.jsx:111` "Export" · `:123` "selected" · `:64` placeholder "e.g. 22, 119a" · `sections-a.jsx:56,140` "OGN · Origins" · `:150` " (name, text, tag, id)" · `sections-b.jsx:19` "orders" · `:111` "12 mo" · `:123` "soon" · `card-modal.jsx:22` "BANNED" · `:31` aria "Close" · `:75` "14 wk →" · `FOIL` (4 sitios) · `helpers.jsx:182,186` `title="exhaust"`/nombre de runa · "Tweaks" |
| Enumeraciones mostradas en crudo (EN) | datos | dominios (7), tipos (7), rarezas (5), condiciones (MT/NM/EX/GD/LP), idiomas (5), estado de venta (`shipped/pending/cancelled`), "Gear" |

### 4.4 Requisitos F1

1. Librería ICU (p. ej. `react-i18next` + ICU, o FormatJS), `I18nProvider` con `lang` desde `Prefs` (BD) y detección inicial del navegador; `<html lang>` dinámico; formato de números/fechas/moneda/plurales por `Intl` con el locale de la app.
2. Namespaces: `common, nav, cards, collection, decks, events, sales, stats, account, auth, admin, enums, errors, validation`. Migrar los ≈ 280 ternarios y las 99 claves usadas.
3. **Enums traducibles** (`enums.domain.Fury`, `enums.rarity.Rare`, `enums.condition.NM`, `enums.event_type.regional`, `enums.sale_status.shipped`, …).
4. Mensajes de validación de mazo y de API por **código + parámetros** (`{code:"copies_over", params:{name,count,max}}`), nunca texto libre del backend; el cliente los traduce.
5. Nombres/habilidades de cartas **no se traducen** (vienen del catálogo oficial en inglés/idioma de la galería): son datos, no UI. Decidir si F2 expone `name_es`/`ability_es` cuando el scraper los tenga.
6. CI: script que falle si falta una clave en un idioma o hay claves sin usar.

---

## 5. Interacciones y reglas a portar (verbatim salvo nota)

> Leyenda de columna **Decisión**: *Port* = portar tal cual; *Adapt* = portar con el cambio indicado; *Move* = mover al backend como fuente única; *Drop* = no portar.

### 5.1 Reglas de mazo (hoy en cliente: `app.jsx:91-213`, `deck-editor.jsx:9-89`)

| Regla | Prototipo | Ref | Decisión |
|---|---|---|---|
| Tamaño | `DECK_TARGET=40`; `mainCount = Σ(main) + (champ?1:0)`; issues "faltan N (x/40)" / "N de más" | `deck-editor.jsx:9,48,61-62` | *Move*; = 39 + campeón (roadmap §3) |
| Runas | exactamente 12 (`RUNE_MAX`); `onDeckSetRune` limita `cap = 12 − otras` | `deck-editor.jsx:10,63`, `app.jsx:167` | *Move* |
| Color de runas | sólo colores de la leyenda (`cols = legend.domains − Colorless`); una fila por color; carta de runa = primera `type==='Rune'` con `domains[0]===color` | `deck-editor.jsx:16-19,406-408` | *Move*; el backend valida también por API |
| Campos de batalla | 3 **distintos**; no cuentan para el mazo; `filter(Boolean)` compacta huecos | `deck-editor.jsx:11,64-65`, `app.jsx:179` | *Move* |
| Banquillo | `SIDE_MAX=8` (bloquea añadir/mover; import `min(…, 8−sideTot)`) | `deck-editor.jsx:13`, `app.jsx:123,133,162,208` | *Adapt* → **10** |
| Copias | 3 por **nombre** (todos los printings): `canAddName` suma main+side+workbench+champ(1) | `app.jsx:130-135` | *Move*. `deckIssues` suma main+side+champ y **omite taller** (`deck-editor.jsx:66-72`): unificar con el roadmap (main+banquillo+taller+campeón) |
| Taller | hasta 100 nombres **distintos**; ≤3 copias por nombre; fuera de export, valor y validación | `app.jsx:132,164`, `deck-editor.jsx:14,76` | *Move* |
| Campeón elegido | `type==='Champion'` y `shareTag(champ, legend)`; al elegirlo, si su nombre ya acumula 3 copias, se quita 1 (main → side → workbench) | `app.jsx:100-109`, `deck-editor.jsx:20,256` | *Move* |
| Cambio de leyenda | purga runas con `domains[0] ∉ cols` y campeón sin tag común; **no** toca el main | `app.jsx:111-117` | *Move*; añadir issue por cartas fuera de identidad |
| Filtro de adición (main) | excluye Legend/Battlefield/Rune; Spell con tags (= Signature Spell) sólo si comparte tag con la leyenda; resto Colorless o dominio ∈ colores; sólo printing base; **no excluye tokens** (`type_raw` Token Unit/Gear) | `deck-editor.jsx:249-254` | *Adapt*: usar `type_raw`, excluir tokens |
| Dominios del mazo | unión de dominios (sin Colorless) de leyenda+campeón+main | `app.jsx:91-96` | *Move* (derivado) |
| Valor | Σ `market×qty` de main+leyenda+campeón+runas+banquillo+campos (sin taller) | `deck-editor.jsx:51-53` | *Adapt*: cadena `avg7_foil→avg7→low_foil→low`, EUR |
| Agrupación / orden | main agrupado por tipo (Unit+Champion, Gear, Spell, Other), A→Z `localeCompare`; export ordena por total desc y nombre | `deck-editor.jsx:36-44,82,87` | *Port* con collation explícita |
| Printing base | misma `name` = misma carta; base = menor `num` puramente numérico (resto con sufijo a/s/t/R) | `data.js` `baseSort` (bloque `PRINT/BASE`) | *Adapt*: `is_base` calculado en servidor |
| Legalidad por modo | **no existe** (`banned` es booleano en la ficha y no interviene) | `card-modal.jsx:22` | F5: ban por **nombre** y modo; mazo marcado "no legal en {modo}" con motivo |
| Silencio de límites | `+`/mover son *no-ops* | `app.jsx:139,144` | *Adapt*: tooltip con motivo |

**Casos de test compartidos (Python + TS) sugeridos** (derivados del prototipo): (a) 3 copias entre printings distintos del mismo nombre; (b) el campeón elegido ocupa una de las 3; (c) elegir campeón con 3 copias elimina 1 (orden main→side→workbench); (d) cambio de leyenda purga runas y campeón incompatible pero no main; (e) banquillo 10 (11.ª rechazada); (f) mover taller→main bloqueado con ≥3 entre main+side+champ; (g) 12 runas exactas / color fuera de leyenda; (h) 3 battlefields distintos; (i) auto-runas (ver 5.3).

### 5.2 Parser de importación de mazo (`app.jsx:180-213`)

1. Línea a línea (`split(/\r?\n/)`), `trim`, ignora vacías.
2. **Cabeceras** (se quitan `:` / `：` finales, minúsculas): `legend(s)|leyenda(s)` → legend; `champion(s)|campeón(es)` → champion; `main deck|maindeck|mazo principal` → main; `battlefield(s)|campo(s) de batalla` → bf; `rune(s)|runa(s)` → runes; `sideboard|banquillo` → side. (No hay cabecera de taller.)
3. **Línea de carta**: `^(\d+)\s*[xX]?\s+(.+)$` → `qty`, `ident`; si no casa, `qty=1`, `ident=línea`. Una línea `Name: X` / `Name=X` fija el nombre del mazo (`/^name\s*[:=]/i`).
4. Se elimina un **paréntesis final** (`\s*\([^)]*\)\s*$`, p. ej. código de set).
5. **Resolución**: si `ident` empieza por `OGN[- ]?\w+` → id `OGN-<resto>` (o `ident.toUpperCase()`); si no, nombre **exacto** (case-insensitive, primera coincidencia del catálogo — **no necesariamente el printing base**), y si no, nombre que **contiene** el texto (primera coincidencia). Sin resolver → **se descarta en silencio**.
6. **Colocación**: sección explícita o, sin sección, por tipo (Legend→legend; Champion→champion; Battlefield→bf; Rune→runes; resto→main). Champion: el primero es el elegido; los siguientes van al main con tope 3. Battlefields ≤3 distintos. Runas ≤12 acumuladas. Banquillo `min(qty, 3−tot, 8−sideTot)`. Main `min(qty, 3−tot)` (tot = main+side+campeón). **No** valida colores de leyenda, no limita a 39, la leyenda gana la última.
7. Crea **un mazo nuevo** (nombre por defecto "Imported deck/Mazo importado"), recalcula `domains`, lo selecciona.

*Port*: la gramática de cabeceras ES/EN, `qty` con `x`, paréntesis final, `Name:`. *Adapt*: moverlo al backend (`POST /decks/import`), prefijo de set dinámico (hoy `OGN` hardcodeado), devolver `warnings` por línea, preferir el printing base y respetar el id explícito, formatos riftdecks/piltover (F5), validación de colores/reglas y sideboard 10.

### 5.3 Auto-runas (`app.jsx:168-178`; el botón dice "Balancear por curva de poder", `deck-editor.jsx:402`, pero el algoritmo balancea por **demanda de color**)

1. `cols` = colores de la leyenda sin Colorless; si no hay leyenda o `cols` vacío → no-op.
2. `demand[c]` = nº de **copias** (main por printing×qty, más el campeón) cuyo dominio incluye `c` (una carta bicolor suma a ambos; leyenda y runas no cuentan).
3. `total = Σ demand`. Si `total==0` → `out[c] = floor(12/|cols|)`; si no → `out[c] = max(1, round(demand[c]/total*12))`.
4. `order` = `cols` ordenadas por `out` desc. Mientras `sum>12`: restar 1 a `order[gi % n]` si `out>1`. Mientras `sum<12`: sumar 1 a `order[gi % n]` (tope de seguridad 200 iteraciones).
5. Sustituye **todas** las runas: por color, la runa (`type==='Rune'`, `domains[0]===c`) con cantidad `out[c]`.

> **Trampa de portado**: JS `Math.round(2.5)=3` pero Python `round(2.5)=2` (banker's). Caso de test: demanda `[5,19]` ⇒ `out=[3,10]` → suma 13 → `[3,9]` (JS). Implementar `floor(x+0.5)` en Python. Igual para `localeCompare` vs colación de Python y para la estabilidad de `sort`.
> Casos adicionales: 1 color → 12; 2 colores sin cartas → 6/6; `[1,100]` → `[1,11]`; `[7,3]` → `[8,4]`.

### 5.4 Formato de export de texto (`deck-editor.jsx:77-89`)

```
Legend:
1 <nombre de la leyenda>

Champion:
1 <campeón elegido>

MainDeck:
<total> <nombre>          (orden: total desc, luego nombre)

Battlefields:
1 <nombre>                (orden de slots)

Runes:
<total> <Nombre de runa>  (orden de inserción)

Sideboard:
<total> <nombre>          (total desc, nombre)
```
Cabeceras **siempre en inglés**, secciones vacías conservan la cabecera, `join('\n').replace(/\n{3,}/g,'\n\n').trim()+'\n'`; sólo nombres (sin ids ni sets: se pierde el printing); sin taller. Fichero `name.replace(/[^\w\-]+/g,'_')+'.txt'`. Ejemplo de import (placeholder, `deck-editor.jsx:94`): Vex, Gloomist / Vex, Apathetic / Defy, Discipline, Sona, Harmonious / Grove of the God-Willow / 7 Calm Rune + 5 Chaos Rune / 2 Hard Bargain.

### 5.5 Operaciones de edición de mazo (semántica exacta)

| Operación | Comportamiento | Ref |
|---|---|---|
| `onDeckAddCard(printingId)` | +1 copia de **ese printing** si `canAddName` | `app.jsx:139-140` |
| `onDeckBump(zone,name,±1)` | `+`: al printing existente con más copias o al base; `−`: del printing con más copias; ambos por **nombre** | `app.jsx:143-147` |
| `onDeckVariant(zone,printingId)` | si caben más copias, añade esa versión; si no, **rota** una copia desde el otro printing con más copias | `app.jsx:150-153` |
| `onDeckRemoveName(zone,name)` | borra todas las copias del nombre en la zona | `app.jsx:156-157` |
| `onDeckMoveName(name,from,to)` | mueve 1 copia conservando printing; bloquea si banquillo lleno, si taller→main/side deja ≥3, o si taller ya tiene 3/100 distintos | `app.jsx:160-165` |
| `onDeckSetBattlefield(slot,id)` | rellena a 3 y compacta | `app.jsx:179` |
| `patchDeck({legend})` / `patchDeck({champion})` | purgas descritas en 5.1; recalcula `domains` | `app.jsx:97-118` |

### 5.6 Eventos: fechas, ICS y Google Calendar (`events.jsx:69-126`)

| Pieza | Comportamiento exacto | Decisión |
|---|---|---|
| Días relativos | `evtRelDays = round((fecha − HOY)/86400000)` con `HOY` **fijo** `'2026-06-01'` (`:5`) | *Adapt*: fecha del servidor / zona del usuario |
| Chip "pronto" | `d<0` ninguno; `0` "Hoy" (tono rojo); `1` "Mañana"; `≤7` "en N días"; `≤14` "en 2 semanas"; más lejos: nada | *Port* con plurales ICU |
| Formato de fecha | larga `weekday short, day, month short, year`; corta `dd mon yyyy`; mes `month long year`; locales `es-ES` / `en-GB` | *Port* (locale de la app) |
| Rango (`evtRange`) | `start = YYYYMMDDTHHMM00`; duración **3 h** (skirmish, nexus, presencial, online) u **8 h** (regional, nacional); `endH = min(23, h+dur)` (se trunca el día) ; hora local flotante (sin zona) | *Adapt*: `starts_at` con TZ + `ends_at` explícito; duración por tipo configurable |
| Google Calendar | `https://calendar.google.com/calendar/render?action=TEMPLATE&text=<name>&dates=<start>/<end>&location=<loc>&details=<det>` (todo `encodeURIComponent`); `loc = ONLINE ? "<venue> · Online" : "<venue>, <city>"`; `det = "Riftbound · <tipo> · <FMT>\nPremio: <prize>\nOrganiza: <org>"`; enlace con `target=_blank rel="noopener noreferrer"` | *Port*; añadir `ctz` y URL del evento |
| ICS (`evtDownloadICS`) | `BEGIN:VCALENDAR / VERSION:2.0 / PRODID:-//Riftbound Manager//Eventos//ES / CALSCALE:GREGORIAN`; por evento `BEGIN:VEVENT / UID:<id>@riftbound-manager / DTSTART / DTEND / SUMMARY / LOCATION (venue\\, city; online: "venue · Online") / DESCRIPTION:Riftbound · <tipo> · <FMT> / END:VEVENT`; `END:VCALENDAR`; separador `\r\n`; MIME `text/calendar;charset=utf-8`; fichero `riftbound-calendario.ics` | *Adapt* (servidor): añadir **`DTSTAMP`** (obligatorio RFC 5545), `TZID`/UTC, escapado de `, ; \\ \n` en TODOS los campos, plegado de líneas a 75 octetos, `URL`, `DESCRIPTION` con premio/organizador; feed suscribible con token |
| "Cerca de mí" | filtra `e.co === account.country` (país del perfil); si `country==='ONLINE'` no filtra; texto del botón = ciudad o país | *Adapt*: distancia/ciudad si hay geodatos |

### 5.7 Colección: CSV, precios, filtros

| Pieza | Prototipo | Decisión |
|---|---|---|
| Export CSV | cabeceras `set,id,name,foil,qty,condition,language,selling,sellPrice,marketPrice`; filas = **todas las filtradas** (no sólo la página); `name` entre `"`, sin escapar comillas internas, `foil/selling` como `true/false`, sin BOM; fichero `riftbound_collection.csv` (`collection.jsx:39-44`) | *Adapt*: formato RBAPP definido en F3 (añadir `purchase_price`), BOM, `csv` de servidor. **Ya existe** `export_csv` Cardmarket (`name,language,quantity,price`, QUOTE_ALL, BOM, fichero `YYYYMMDDHHMMSS_set_rareza.csv`) e `import_csv` (`set;id;foil;qty`) — preservar compatibilidad |
| Precio de venta por defecto | `market × 1.05` (2 decimales) al activar `selling` sin precio, en alta, tabla, móvil y modal (`collection.jsx:36,147,177`, `card-modal.jsx:106`) | *Port* como valor por defecto configurable |
| Orden | `set`(= `num.padStart(5,'0')`, léxico), `name`, `price` (market de la carta, no del precio de venta), `qty`, `updated`, `rarity` (alfabética, no por rareza real) | *Adapt*: orden numérico por número y por rareza (Common<…<Showcase) en servidor |
| Filtros | `Set`, `Card ID` (substring de `num`), `Card name` (substring), avanzados: dominio (incluye), tipo, rareza, foil (any/foil/plain), selling (any/selling/not); cualquier cambio vuelve a página 0 | *Port* → query params |
| Alta | **cada Add crea una línea nueva** (no suma a existentes) | *Adapt*: decidir si fusionar líneas idénticas (set,id,foil,condición,idioma) |
| `Playset` | `qty >= 3` → badge "Yes" (calculado) | *Conflicto* con `rbcol_playset` (§6, §10-1) |
| Valor total de cabecera | Σ `market × qty` de filas filtradas | *Port* con cadena de precios |

### 5.8 Otras interacciones

- **Hover** de tile: `translateY(-4px)`, borde accent, sombra; filas de tabla `rgba(120,205,228,.05)`; `.ws-row` borde accent (`riftbound.css:220,234,341`).
- **Modales**: Esc (sólo CardModal), clic en fondo, bloqueo de scroll del `body` (sólo CardModal).
- **Clipboard** y **descargas**: ver §2.6.
- **Navegación**: `scrollTo({top:0})` al cambiar de sección (`app.jsx:82`).
- **Persistencia del prototipo** (a sustituir por BD salvo preferencias efímeras): `rb_lang`, `rb_route`, `rb_inv_v3`, `rb_decks_v2`, `rb_account_v1`, `rb_evt_tab`, `rb_evt_saved`, `rb_evt_manual`.
- **Pestaña de evento** y **subsección de cuenta**: persistir en la URL, no en `localStorage`.


---

## 6. Conflictos con las decisiones del roadmap (el roadmap manda)

| # | Comportamiento del prototipo (ref) | Comportamiento decidido | Impacto / fase |
|---|---|---|---|
| 1 | Banquillo **8** (`deck-editor.jsx:13`, `app.jsx:123,133,162,208`; textos "(x/8)") | **10** (roadmap §3). Valor sólo en `GET /rules` | F5. Cambiar constantes, import, UI y tests |
| 2 | Baneo = booleano `card.banned` + badge "BANNED" (`card-modal.jsx:22`); BD `rbcar_banned` 'Y/N' | Ban por **modo (`1v1`,`2v2`) y por nombre** (todas las versiones); UI indica modo; mazo "no legal" con motivo | F2 (ficha, catálogo), F5 (legalidad), F10 (admin de baneos). Tabla nueva de bans; `DeckSummary.legal` por modo |
| 3 | Selector de proveedor (Cardmarket/Cardtrader/TCGplayer) y moneda (EUR/USD/GBP/JPY) (`account.jsx:511-528`, `ACC_CUR`) | **Sólo Cardmarket, EUR**: selector oculto | F1/F9. `formatMoney` fijo EUR; eliminar `account.pricing`; `money0` con `€` prefijo → unificar |
| 4 | Precios estimados por rareza + PRNG por id (`data.js`), `est`/`recommended`/`est_prices_note` | Precios reales Cardmarket; cadena `avg7_foil → avg7 → low_foil → low`; Basic Rune sin foil; carpeta de imagen por prefijo (fix `1ae1f6e`) | F0/F2. `price.source` indica qué eslabón se usó; quitar textos "est." |
| 5 | Histórico 14 puntos sintético "14 wk" (`card-modal.jsx:75`) | Histórico real de `rbcm_price` con rangos | F2 (ficha), F4 (snapshots diarios) |
| 6 | Serie de valor de colección sintética de 12 meses (`data.js` `VALUE_HISTORY`) | Snapshot diario por usuario; KPIs + gráfico 12 m | F4. Backfill imposible → gráfico arranca el día del primer snapshot (empty-state "recopilando datos") |
| 7 | Todo en `localStorage` (inventario, mazos, cuenta, eventos) | API JSON `/riftbound/api/v1/*`; **offline sólo lectura**: catálogo, colección y mazos; ediciones requieren red | F1 (SW + IndexedDB + TanStack Query persist), F2-F8. UI de edición debe mostrar "sin conexión" y deshabilitar acciones |
| 8 | Mono-set OGN: `RB.SETS[0].total` (`sections-a.jsx:49`), eyebrows "OGN · Origins" (`sections-a.jsx:56,140`, `sections-b.jsx:103`, `events.jsx:558`), `aSet` por defecto 'OGN', regex de import `OGN[- ]?` (`app.jsx:198`), `RUNE_BY_COLOR` primera runa | **Varios sets**; clave de carta `(set_id, card_id)` | Todas. Rutas `/cards/:set/:id`; selector de set en filtros; parser de import por set; runas por set |
| 9 | Sólo 5 imágenes reales (`CARD_IMG`, `helpers.jsx:126-132`), placeholder 3:4 | Imagen real por `RbCard.image_src` (carpeta por prefijo de fichero); placeholder sólo como fallback | F2. 352×492 (≈5:7); generar derivados webp/miniaturas; SW cachea imágenes con límite |
| 10 | Sin autenticación; el botón Logout no hace nada (`app.jsx:247`); no hay login/registro | Multiusuario; cookie same-origin + CSRF; registro abierto con límite de intentos + CAPTCHA + bloqueo de cuenta; Discord/Google; admin = propietario | F0 (backend), F1 (pantallas), F9, F10. **No hay diseño**: crearlo con los tokens |
| 11 | Varios correos con "Verificar" que lo marca verificado al instante (`account.jsx:94,154-187`) | **Sin servidor de correo** → no hay verificación ni recuperación por email; admin restablece contraseñas | F9. Quitar lista de emails; como mucho un contacto opcional sin verificar (decisión §10-2) |
| 12 | 2FA = switch + QR de relleno + código fijo (`account.jsx:362-377`) | **2FA TOTP** real | F9. QR, verificación, códigos de recuperación, reto en login |
| 13 | Dispositivos estáticos (`DEFAULT_ACCOUNT.devices`) | Tabla de **sesiones en servidor** | F9. Lista, "este dispositivo", revocar una / todas |
| 14 | Cuentas conectadas: Discord, Google, Metafy, Cardmarket (toggle local) | **Discord y Google** OAuth (guiar al usuario en la creación de las apps) | F9. Metafy/Cardmarket quedan como enlaces de perfil (redes) |
| 15 | Invitaciones por email, 5/mes (`account.jsx:221-242`) | No existe (no hay correo ni suscripciones) | F9: **eliminar** |
| 16 | Planes Free/Standard/Advanced y métodos de pago (`ACC_PLANS`, `PaymentMethods`) | **Sin pagos ni plan** | F9: **eliminar**; la "API key" deja de ser feature de pago |
| 17 | API key generada en cliente (`rb_live_` + 20 bytes hex) y guardada en claro (`account.jsx:441-444`) | API key (F9) | Generar en servidor, guardar **hash**, mostrar una vez, `last_used_at`; autenticación por cabecera para scripts |
| 18 | Eventos manuales en `localStorage`, semilla fija (`events.jsx:26-60,531-546`) | Manual **privado/público** a elegir + importados del scraper (siempre públicos); guardados; resultado + mazo; ICS; Google Calendar; recordatorios push | F8. `visibility`, `source`, dueño; edición/borrado sólo del dueño; moderación pública (admin) |
| 19 | Historial = ganador del torneo (`events.jsx:446-464`) | Resultado propio + mazo jugado | F8. Vincular `deck_id`; estadísticas de rendimiento |
| 20 | Ventas con `cost` obligatorio y sin crear venta desde listing (`sections-b.jsx:53-66`) | **Precio de compra opcional** por línea; margen real si existe, si no comparación con mercado del día; vender descuenta inventario; export compatible Cardmarket | F3 (campo), F7 |
| 21 | `selling` booleano por línea + "Playset" = `qty>=3` (`collection.jsx:146-147`) | (no decidido) El backend ya modela **`rbcol_playset ∈ {1,2,3}`** con prioridad foil y auto-selling del sobrante (`collection.py:400-572`) | Decidir en F3 (§10-1); afecta tabla, ficha y export Cardmarket (`qty − playset`) |
| 22 | `deck.valid` almacenado; issues como cadenas ES/EN (`deck-editor.jsx:57-74`) | Reglas en backend; legalidad por modo; mensajes por código | F5 |
| 23 | Import/export sólo del formato propio (`Legend:/Champion:/MainDeck:…`) | + formatos riftdecks.com y piltoverarchive.com; vista previa con avisos | F5 (pedir ejemplos al usuario como en F3) |
| 24 | Mazos sin relación con la colección (README gap 5) | **Mazo vs colección** (faltantes + coste) | F5 |
| 25 | Mazos sin `mode`; sin versiones (el backend sí tiene `rbdck_mode`, `rbdck_seq`, `rbdck_snapshot`) | Modo 1v1/2v2 por mazo; **diff de versiones**; enlace público de sólo lectura; simulador de mano; **migración automática** de mazos existentes al formato v2 | F5 |
| 26 | Preferencias de interfaz en panel de tweaks / `localStorage` | Densidad, acento, intensidad de fondo, idioma, vista por defecto **en BD** | F1 (+ UI en Account → Interfaz, hoy incompleta) |
| 27 | Idioma por defecto EN, sólo en topbar, `localStorage` | ES/EN reales, en BD, con detección | F1 |
| 28 | Router por estado (`rb_route`) | Rutas reales con deep-link, `ErrorBoundary`, 404 | F1 |
| 29 | Fechas fijas (`EVT_TODAY`, `updated:'2026-05-30'`) | Fecha del servidor | Todas |
| 30 | Moneda/formatos con locale del navegador | Locale de la app | F1 |
| 31 | Fuentes por Google Fonts | Autohospedadas (Manrope, Space Grotesk) | F1 |
| 32 | Sin importación de colección (sólo export) (README gap 3) | **Asistente de importación CSV** (RBAPP, Cardmarket, riftdecks, piltoverarchive, otras) | F3 (pedir ejemplos) |
| 33 | Catálogo/cartas con `Token Unit/Gear` mezclados como Unit/Gear (`data.js`: 8+2; ids `OGN-t0x`; los mazos de ejemplo los usan en el main) | Catálogo oficial del scraper (`rbcards`) | F2/F5: decidir si los tokens existen en BD y excluirlos del deck builder |
| 34 | Condiciones MT/NM/EX/GD/LP e idiomas (5) cerrados | Export compatible Cardmarket (grados y 10+ idiomas) | F3/F7: ampliar enumeraciones desde `/meta` |
| 35 | Tweaks `accent:'mixed'` | No existe en producto | Descartar |
| 36 | Pantallas de administración no existen | Sets, edición de cartas, carga Cardmarket, mappings, ignorados, usuarios (bloquear, reset de contraseña), baneos por modo | F10: diseñar (escritorio) |

---

## 7. Gaps del prototipo (estados, validación, confirmaciones, a11y, responsive, bugs)

> Severidad: **A** = bloqueante para entrega / WCAG A-AA, **M** = media, **B** = baja. "Fase" = dónde corregirlo.

### 7.1 Estados ausentes

| ID | Gap | Evidencia | Sev. | Fase |
|---|---|---|---|---|
| S1 | **Sin estados de carga/skeleton** en ninguna pantalla (todo es síncrono) | `data.js` global; ningún `loading` | A | F1 (componentes) + cada fase |
| S2 | **Sin estados de error/red/offline** (ni banner "solo lectura", ni reintento) | — | A | F1 |
| S3 | Vacíos: sólo "My calendar" está bien diseñado; resto usa `.empty` genérico. Faltan: dashboard de usuario nuevo, mazos vacíos (hay hint), catálogo sin resultados con mensaje correcto, historial, ventas | `events.jsx:481`, `sections-a.jsx:221` (usa `not_in_collection`) | M | F1/F2/F3/F8 |
| S4 | Sin toasts/feedback de guardado (ediciones inline silenciosas) | `collection.jsx:145-153` | M | F1 |
| S5 | Sin paginación en servidor/offline; catálogo completo en memoria | — | M | F2 |

### 7.2 Validación de formularios

| ID | Gap | Evidencia | Sev. | Fase |
|---|---|---|---|---|
| V1 | Precio de venta acepta negativos/NaN (`type=number` sin `min`) | `collection.jsx:92,148`, `sections-b.jsx:39`, `card-modal.jsx:103` | M | F3/F7 |
| V2 | Cantidad sin entrada directa ni máximo; en tabla mínimo 1 | `collection.jsx:90,145` | B | F3 |
| V3 | Nombre de mazo vacío/duplicado permitido; se parchea en cada tecla | `deck-editor.jsx:439` | M | F5 |
| V4 | Evento: sin validar fecha ≥ hoy, plazas/inscripción negativas, URL; sin mensajes de error (sólo botón deshabilitado) | `events.jsx:208,262-267` | M | F8 |
| V5 | Perfil: usuario sin reglas (longitud, unicidad, caracteres); redes sin validar URL; avatar "máx 2 MB" no se valida | `account.jsx:134,193-198,86-87` | M | F9 |
| V6 | Contraseña: texto dice "números y símbolos" pero sólo se exige longitud ≥ 8 (`:346` vs `:335`); sin medidor ni política | `account.jsx:335,346` | M | F9 |
| V7 | Email: sólo regex simple | `account.jsx:42` | B | F9 |
| V8 | Los formularios no enlazan error↔campo (`aria-describedby`, `aria-invalid`) | todo | A | F1 (`<Field>`) |

### 7.3 Confirmaciones destructivas

| ID | Gap | Evidencia | Sev. | Fase |
|---|---|---|---|---|
| D1 | Borrar línea (papelera) y borrado masivo **sin confirmar** y sin deshacer; la selección sobrevive a cambios de filtro/página → puede borrar filas no visibles | `collection.jsx:12,124,153,180` | **A** | F3 (`ConfirmDialog` + toast "Deshacer" + selección acotada) |
| D2 | Borrar mazo usa `window.confirm` nativo (no accesible/estilable) | `deck-editor.jsx:468` | M | F5 |
| D3 | Borrar evento manual sin confirmar | `events.jsx:194` | M | F8 |
| D4 | Revocar sesión, desconectar cuenta, eliminar email, regenerar/revocar API key sin confirmar | `account.jsx:96,214,389,469-470` | M | F9 |
| D5 | Quitar carta/nombre de una zona de mazo sin deshacer | `deck-editor.jsx:341` | B | F5 (toast deshacer) |
| D6 | Borrado de cuenta: doble paso + 10 días (**bien**) | `account.jsx:400-411` | — | F9 (decidir §10-3) |

### 7.4 Accesibilidad (WCAG 2.2)

| ID | Gap | Evidencia | Sev. |
|---|---|---|---|
| A1 | Sólo **4 usos de ARIA** en toda la app: `role="dialog" aria-modal` y `aria-label="Close"` (CardModal), `aria-expanded` (CollapseSection), `role="button"` (avatar) | `card-modal.jsx:16,31`, `deck-editor.jsx:168`, `account.jsx:113` | A |
| A2 | `<label>` **no asociado** a ningún control (sin `htmlFor`, sin anidar) | `collection.jsx:60-96`, `events.jsx:223-270,335-428`, `account.jsx:131-352,513-520` | A |
| A3 | Navegación con `<a>` **sin `href`** ni `role`; no hay `aria-current`; la marca es un `div` clicable | `app.jsx:226,231,272` | A |
| A4 | Modales: sin focus trap/retorno de foco; Import/Export/AddEvent sin `role`, Esc ni scroll lock; botones de cierre `×` sin `aria-label` | `deck-editor.jsx:96-101,123-128`, `events.jsx:213-220` | A |
| A5 | `CardPicker` no es combobox ARIA ni usable con teclado | `sections-a.jsx:5-37` | A |
| A6 | Elementos clicables que son `div`/`td`/`span` (tiles, `ws-row`, `deck-card`, `thumb`, `cell-name`, `switch`) | `sections-a.jsx:85,182`, `collection.jsx:140,143,147,192`, `deck-editor.jsx:204` | A |
| A7 | Botones sólo-icono con `title` y sin `aria-label`; toggles sin `aria-pressed` (bookmark, chips, seg, switch) | `events.jsx:158-161,194`, `deck-editor.jsx:293,337-341,383`, `account.jsx:174,303` | A |
| A8 | `Switch` sin `role="switch"/aria-checked`; los `span.switch` no son focusables | `account.jsx:61-67`, `collection.jsx:89,147,177` | A |
| A9 | **Foco**: sin `:focus-visible` en botones/links/chips; el anillo de inputs (alfa 14 %, cian fijo) no llega a 3:1 | `riftbound.css:147-149` | A |
| A10 | **Contraste** (calculado sobre `--bg-0`/`--panel`): `--muted-2` sobre panel **4.26:1** (<4.5) en texto 11-12 px (labels `.k`, `.tiny muted`, placeholders ok 5.05); texto blanco de `.btn-logout` 4.14; badges de evento `nacional` 3.29 / `nexus` 3.21; `--red` como texto sobre fondo 3.98; texto `#06222c` sobre chip Epic 3.88; glifo blanco de `DomainPips` sobre Order 1.93, Colorless 2.65, Body 2.67, Calm 2.69, Fury 3.72, Mind 3.57 | `riftbound.css` varios, `events.jsx:129` | A |
| A11 | Texto < 11 px (9–10.5 px) pese a la regla del README | `riftbound.css:275,293,325,373,379,394,703,709,714` | M |
| A12 | **Targets < 24 px** (WCAG 2.5.8): `.stepper.sm button` 22×22, botones de `.ws-actions` 22×22, `.varchip` 20 px de alto; `.ws-x/.ws-move/.ws-wb` (24×24) están justo en el mínimo | `riftbound.css:361,364,371,343,350` | A |
| A13 | Gráficos (Sparkline, PriceChart, Donut, MiniCurve, barras) sin alternativa textual; significado up/down sólo por color en tiles (el signo `+/-` ayuda) | `helpers.jsx:204-246` | A |
| A14 | `DomainPips`/`RarityDot`/tokens de habilidad dependen de `title` y de glifos | `helpers.jsx:117-123,182-186` | M |
| A15 | Sin `aria-live` para "Copiado", validaciones y toasts; `CopyBtn` muestra éxito aunque falle | `account.jsx:69-74`, `deck-editor.jsx:120` | M |
| A16 | SPA sin gestión de foco/`document.title` al cambiar de ruta; `lang` fijo `en` | `app.jsx:82`, HTML | A |
| A17 | **Sin `prefers-reduced-motion`** (foil infinito, animaciones de modal, hover) | `riftbound.css:183-185,262-266` | M |
| A18 | Sin `color-scheme: dark` (date/time/select/checkbox claros); sin estilo de scrollbar en Firefox | `events.jsx:241-243` | M |
| A19 | Tablas sin `<caption>`/`scope`; checkbox de fila sin nombre accesible; "seleccionar todo" ausente | `collection.jsx:132-139` | M |
| A20 | Foco al abrir modal (`autoFocus` sólo en AddEvent) y orden de tab del workspace de mazo (decenas de paradas) | — | M |

### 7.5 Responsive y plataforma

| ID | Gap | Evidencia | Sev. | Fase |
|---|---|---|---|---|
| R1 | Dashboard: grid inferior con estilo inline `1.2fr 1fr` **sin media query** → 2 columnas aplastadas en móvil | `sections-a.jsx:80` | A | F4 |
| R2 | Tabla del catálogo oculta ≤680 (`.collection-table`) **sin lista alternativa** → pantalla vacía en vista tabla | `riftbound.css:433`, `sections-a.jsx:197` | A | F2 |
| R3 | Tablas con `min-width` (920/900/760) → scroll horizontal en móvil y tablet 681-960 (Historial de eventos, Ventas, Colección) | `riftbound.css:228`, `events.jsx:439`, `sections-b.jsx:52` | M | F3/F7/F8 |
| R4 | **Sales** inaccesible en móvil (no está en `BOTNAV`); Dashboard sólo por la marca | `app.jsx:24` | A | F1 |
| R5 | Placeholder `3/4` vs imagen `352/492`; `cqw` depende de que cada llamador añada `containerType` | `riftbound.css:197`, `helpers.jsx:136,149` | M | F2 |
| R6 | `thead th{position:sticky;top:0}` dentro de `overflow-x:auto` → el sticky es relativo al wrapper, no a la ventana (el README lo describe "bajo la topbar") | `riftbound.css:227-229` | M | F3 |
| R7 | `100vh` (body, shell, modal móvil) → barras dinámicas móviles; sin `env(safe-area-inset-top)` en PWA standalone | `riftbound.css:54,80,443`, HTML `viewport-fit=cover` | M | F1 |
| R8 | Contenedor fijo 1280; `padding-bottom:110px` también en desktop | `riftbound.css:36,136` | M | F1 (§3.0) |
| R9 | Decks <960: el workspace se inserta **inline bajo la tarjeta seleccionada** (scroll largo); cambiar de mazo reinicia secciones colapsadas | `deck-editor.jsx:220` | B | F5 |
| R10 | `backdrop-filter` en cada `.panel` + sombras grandes por carta → coste en móviles de gama baja; falta `@supports not (backdrop-filter)` | `riftbound.css:134,84,261` | B | F1 |

### 7.6 Bugs / lógica a **no** portar

| ID | Bug | Evidencia |
|---|---|---|
| L1 | Stats: variación 12 m compara el **valor real actual** con el primer punto de una serie sintética | `sections-b.jsx:111` |
| L2 | `Donut` con un único segmento no dibuja nada (arco con inicio=fin) | `helpers.jsx:239-243` |
| L3 | `PriceChart`: `id="pcg"` repetido y `preserveAspectRatio="none"` deforma círculo/trazo | `helpers.jsx:227,226` |
| L4 | Icono "Prev" apunta a la derecha | `sections-a.jsx:174` |
| L5 | Mensaje de catálogo vacío = "Aún no está en tu colección" | `sections-a.jsx:221` |
| L6 | `className` duplicado (`mt` + `dist-grid`) en Stats; `mt` se pierde | `sections-b.jsx:149` |
| L7 | Alta de colección: el select Set no filtra el picker; ordenación `set` léxica; orden por precio usa mercado de la carta; ordenación por rareza alfabética | `collection.jsx:8,24,87-88` |
| L8 | ICS sin `DTSTAMP`, sin escapado general, hora flotante, fin truncado a 23:xx; GCal sin `ctz` | `events.jsx:95-126` |
| L9 | `deckIssues` ignora taller en el tope de copias (inconsistente con `canAddName`) | `deck-editor.jsx:66-72` vs `app.jsx:131` |
| L10 | Tooltip de "Auto" runas dice "curva de poder" y hace demanda de color | `deck-editor.jsx:402` |
| L11 | Import descarta líneas sin avisar y elige la primera coincidencia de nombre | `app.jsx:199-201` |
| L12 | `navigator.clipboard` ausente en HTTP; se muestra "Copiado" igualmente | `account.jsx:71`, `deck-editor.jsx:120` |
| L13 | `FilterChips` stub, `fontScale`/`fs`, `minus/menu/edit/ticket`, `.icon-btn`, `.hamburger`, `valid` almacenado: código muerto | varios |
| L14 | `scheduleDelete` guarda `deletionScheduled: Date.now()` del cliente (reloj local) y la cuenta atrás se calcula en cliente | `account.jsx:339,422` |
| L15 | Nombre de mazo se persiste por pulsación; en servidor: debounce/blur | `deck-editor.jsx:439` |


---

## 8. Assets y tipografías

### 8.1 Ficheros del handoff

| Fichero | Dimensiones | Tamaño | Uso en el prototipo | Acción en producción |
|---|---|---|---|---|
| `design/assets/new_rift.webp` | **1920×1079**, WebP VP8 lossy | 189 822 B (≈185 KB) | Capa `.app-bg::before` (mapa de Runeterra), opacidad 0–1 | Copiar al build, precache del service worker. Valorar variante ≈1280 px para móvil (`image-set`) |
| `design/assets/cards/OGN-1.png` | **352×492**, PNG | 259 629 B | Único arte real de OGN-1 | **No usar** en producción (imágenes vienen de `RbCard.image_src`); útil como fixture de tests/screenshots |
| `design/assets/cards/OGN-2.png` | 352×492 | 279 981 B | idem | idem |
| `design/assets/cards/OGN-12.png` | 352×492 | 245 651 B | idem | idem |
| `design/assets/cards/OGN-28.png` | 352×492 | 296 889 B | idem | idem |
| `design/assets/cards/OGN-29.png` | 352×492 | 272 069 B | idem | idem |
| *(suma de las 5 cartas)* | — | 1 354 219 B (≈1.29 MB, media ≈ 270 KB) | — | Referencia de peso: miniaturas (40×54), tiles (≈150 px) y ficha necesitan derivados webp/avif distintos; el SW debe cachear con límite (LRU) para el modo offline |
| `data/20260503_riftbound_cards_coma.csv` | 965 líneas | 185 800 B | Fuente del catálogo OGN | **No se importa** (roadmap §6) |
| `design/data.js` | 35 líneas (una de 169 KB) | 181 630 B | 425 cartas OGN, 48 líneas de inventario, 3 mazos de ejemplo (12 entradas, sin runas/campos/banquillo), 10 ventas (8 shipped, 1 pending, 1 cancelled), historial sintético | **No se porta**; sólo sirve como forma de datos de referencia |
| `design/tweaks-panel.jsx` | — | 24 572 B | Herramienta del entorno de diseño | **No se porta** |
| `design/Riftbound Manager.html` | — | 1 797 B | Shell: React 18.3.1 UMD, Babel standalone, Google Fonts, `viewport-fit=cover` | Sustituir por `index.html` de Vite |

Faltan assets de **PWA** (no hay manifest, favicon, iconos 192/512/maskable, `apple-touch-icon` 180, ni splash): generarlos a partir de la marca (recuadro con `◆`, degradado `linear-gradient(150deg,#2ec6e6,#1c8aa6)`, tinta `#04222b`, aro `rgba(95,224,255,.4)`; `theme_color`/`background_color` = `#06222c`). No hay logotipo oficial (README) → mantener `◆` + texto hasta que exista.

### 8.2 Pesos de fuente a autohospedar

| Familia | Pesos usados realmente | Cargados en el `<link>` | Notas |
|---|---|---|---|
| **Manrope** | **400** (herencia), **600**, **700**, **800** | 400/500/600/700/800 | 500 no aparece en CSS ni inline (`fontWeight` 600×1, 700×16, 800×8) |
| **Space Grotesk** | **600** (`.cardart .name`), **700** (todo `--font-display`) | 500/600/700 | 500 no se usa (el README dice "Manager" 500, el CSS usa 700) |

Recomendación: un **woff2 variable por familia** (Manrope `wght 400–800`; Space Grotesk `wght 600–700`), subset `latin` (+ `latin-ext` bajo demanda) con `unicode-range`, `font-display:swap`, `<link rel="preload" as="font" crossorigin>` sólo para Manrope latin. Licencia OFL para ambas. Mono: `ui-monospace,Menlo,monospace` (sin descarga). Sin pesos itálicos (`.reminder` usa `font-style:italic` sintético sobre Manrope: aceptable, o añadir cursiva si molesta).

---

## 9. Mapeo a las fases del roadmap (qué se construye/porta dónde)

### F0 — Base (sólo contratos que afectan al frontend)
- Formato de error API: `{success:false, error, message, code, params}` (código + parámetros para i18n; §4.4-4).
- `rbcol_quantity` → entero (los steppers asumen número; hoy es `Text`, `models/collection.py:18`).
- CSRF utilizable desde `fetch` (cabecera/cookie) y 401/403/423 (cuenta bloqueada) diferenciados.
- `is_admin` en `GET /me` (F10). Fix `1ae1f6e` (cadena de precios, imagen por prefijo) conservado en `CardSummary.price`/`image_src`.

### F1 — Estructura de la app
- **Portar**: `riftbound.css` completo → capas CSS (`tokens.css`, `base.css`, `components/*.css` o CSS Modules/vanilla-extract), `tokens.ts`, `breakpoints.ts`, fondo `new_rift.webp`, fuentes autohospedadas, `Icon` (47), `DomainPips`, `RarityDot`, `StatCard`, `PageHeader`, `Stepper`, `Switch`, `SegmentedControl`, `Chip`, `Badge`, `Button`, `Field/Input/Select/Textarea`, `Avatar`, `Pagination`, `DataTable`, `Modal/Sheet/ConfirmDialog`, `EmptyState`, `CopyButton`, util `format.ts`, `downloadFile`.
- **Construir (no existe en el prototipo)**: `Skeleton`, `ErrorState`, `OfflineBanner`, `Toast` (+ deshacer), `ErrorBoundary`, 404; foco visible global, `prefers-reduced-motion`, `color-scheme`, safe-area superior, `dvh`.
- **Diseñar con los tokens**: login, registro (CAPTCHA, límite de intentos, cuenta bloqueada), reto 2FA, botones Discord/Google.
- **Shell**: `Topbar`, `BottomNav` (+ "Más"), `AppShell`, rutas, i18n ES/EN (§4), preferencias en BD (densidad, acento con `--accent-rgb`, intensidad de fondo 0–100, idioma, vista por defecto), PWA (manifest, iconos, SW: precache del shell + SWR para GET + cache-first de imágenes con límite), Nginx + HTTPS.
- **API**: `GET /me`, `PATCH /me/prefs`, `GET /meta` (reglas, enums, sets), `POST /auth/*`.

### F2 — Catálogo
- **Portar**: `CardsCatalog`, `CardModal`, `CardArt` (→ `CardImage` + `CardArtPlaceholder`, §2.2), `renderAbility` (→ `AbilityText`/`parseAbility`, §2.3), `CardPicker` (→ `CardCombobox`, ARIA 1.2), `Sparkline`, `PriceChart` real, tira de "relacionadas".
- **Construir**: panel lateral de filtros con facetas y contadores, orden, tabla de catálogo con fallback móvil, vista previa en panel derecho ≥1600, printings de la ficha, bans por modo, "mis copias", histórico real (`/cards/{set}/{id}/prices`), snapshot de catálogo para offline.
- **Desktop**: ver §3.4 y §3.5.

### F3 — Colección
- **Portar**: `Collection` (filtros, alta, tabla, grid, vista móvil en cards), `Stepper`, selección múltiple, `exportCSV` (rehacer en servidor), regla de precio de venta ×1.05.
- **Construir**: edición en bloque, **asistente de importación CSV** (diseño nuevo), wishlist, campo **precio de compra**, `ConfirmDialog`+deshacer, selección acotada, resumen con P/L, tabla con columnas extra en escritorio.
- **Decidir**: semántica `playset`/`selling` (§10-1). Pedir CSV de ejemplo (riftdecks, piltoverarchive, otras).

### F4 — Precios + Dashboard
- **Portar**: `Dashboard` (KPIs, movers, ventas recientes), `Sparkline`, `PriceChart`.
- **Construir**: gráfico 12 m real con hover y rangos, snapshot diario, "cartas que más suben/bajan 7/30 d", watchlist + alertas push (UI de permisos y centro de notificaciones), rail de escritorio (§3.3), estado vacío de usuario nuevo, responsive del grid inferior (R1).

### F5 — Mazos v2
- **Portar**: toda la lógica de `app.jsx:91-213` y `deck-editor.jsx` (reglas §5.1, parser §5.2, auto-runas §5.3, export §5.4, operaciones §5.5) **al backend + librería TS con casos de test compartidos** (incluida la trampa de redondeo y collation). UI: `Decks`, `DeckWorkspace`, `CollapsibleSection`, `MiniCurve`, variant strips, `ImportModal`/`ExportModal`.
- **Cambiar**: banquillo 10, modo 1v1/2v2 y legalidad por nombre, issues por código, taller en el tope de copias, tooltips de límite.
- **Construir**: formato v2 (leyenda, campeón, main, runas, campos, banquillo, taller), migración automática, mazo vs colección, diff de versiones, enlace público (solo lectura), simulador de mano, import/export riftdecks/piltover, panel de análisis (curvas, `Donut` tipo/dominio, valor, faltantes) en 3 columnas ≥1600.

### F6 — Stats
- **Portar**: `Stats` (valor 12 m, completado por set, Donut dominio/rareza, barras por tipo, top valor, movers).
- **Construir**: toggle cantidad/valor, valor por set, matriz set×rareza, top P/L, `Donut` con caso 100 %; layout 2×2 ≥1240 y 4 columnas ≥1600.

### F7 — Sales
- **Portar**: `Sales` (KPIs, listings con precio editable y comparación con mercado, historial con badges de estado).
- **Construir**: crear venta desde un listing (descuenta inventario), margen real si hay precio de compra / comparación con mercado del día si no, export compatible Cardmarket (reutilizar `export_csv`), filtros y gráfico de ingresos/margen, tabla densa en escritorio.

### F8 — Events
- **Portar**: `Events` (tabs, `EventCard`, filtros, `TypeChips`, history, calendar, `AddEventModal`), utilidades de fecha, GCal, ICS (§5.6, mejorado).
- **Construir**: eventos manuales privado/público, importados del scraper (públicos), guardados en BD, resultado + mazo jugado, recordatorios push, vista mes, filtros en panel lateral, KPIs de rendimiento.

### F9 — Account
- **Portar**: `Account` (shell con subsecciones como rutas), `SCard`, Profile (avatar, datos, país/ciudad, redes), Security (contraseña), API key, Interface.
- **Real**: TOTP, sesiones en servidor, OAuth Discord/Google (guía paso a paso), API key con hash, avatar en servidor.
- **Eliminar**: planes, pagos, invitaciones, multi-email con verificación, proveedor/moneda; **añadir** a Interface densidad, acento e idioma.

### F10 — Admin (sin diseño en el handoff)
- Diseñar con tokens para escritorio (tablas densas, formularios en 2–3 columnas): sets, edición de cartas, carga Cardmarket, mappings, ignorados, usuarios (bloquear, reset de contraseña), **baneos por modo**, moderación de eventos públicos.

### F11 — Cierre
- Landing `/` con el estilo nuevo + botón "Instalar app" (`beforeinstallprompt` y guía iOS), retirar Jinja, **auditoría a11y** contra §7.4 (checklist), pasada de rendimiento (`backdrop-filter`, imágenes), Lighthouse PWA, documentación final.

---

## 10. Decisiones abiertas (a resolver al llegar a cada fase)

| # | Pregunta | Recomendación | Fase |
|---|---|---|---|
| 1 | **Playset/selling**: ¿mantener el modelo del backend (`rbcol_playset` 1–3 con prioridad foil y autoventa del sobrante, `qty − playset` en el export) o el del prototipo (`selling` booleano por línea, "Playset" = qty ≥ 3)? | Mantener el del backend (ya alimenta el export Cardmarket) y exponerlo como control "copias que me quedo" en tabla/ficha | F3/F7 |
| 2 | Email: ¿quitar la gestión de emails o dejar un único contacto opcional **sin verificar**? | Un único email opcional informativo; login por usuario/OAuth | F9 |
| 3 | ¿Mantener el borrado de cuenta programado a 10 días? | Sí (ya diseñado), con tarea programada en servidor y reloj del servidor | F9 |
| 4 | Redes sociales y "página de vendedor/perfil público": ¿existirán? El texto del prototipo promete perfil público y listados con avatar | Si no hay perfil público, ocultar redes o dejarlas como enlaces privados | F9 |
| 5 | Tipos/formatos de evento del prototipo (regional, nacional, skirmish, nexus, presencial, online; 1v1/2v2; países ES/FR/PT/GB/DE/IT) vs lo que entrega el scraper | Ajustar enums a los datos reales; formatos alineados con los modos de baneo | F8 |
| 6 | Breakpoint y ancho de escritorio amplio (propuesta: `2xl ≥1600`, `--maxw-wide ≈1760`) | Aprobar propuesta (§1.6, §3.0) | F1 |
| 7 | Defaults de producto: densidad (compact vs regular), acento (orange vs cyan), vista de colección (grid vs table), intensidad de fondo | El prototipo final se ve con compact+orange+grid+100 %; README sugiere regular+cyan. Elegir y guardar como defaults de `Prefs` | F1 |
| 8 | Tokens (`Token Unit/Gear`), Basic Runes y "printing base" (menor `num` numérico): ¿cómo los representa `rbcards`? | Excluir tokens del buscador del deck builder; `is_base` calculado; runas sin foil | F2/F5 |
| 9 | Navegación móvil: ¿qué va en "Más" (Dashboard, Sales, Account, Admin, idioma, logout, instalar)? | "Más" como hoja inferior | F1 |
| 10 | Presupuesto de caché offline de imágenes (catálogo × ≈270 KB sin derivados) | Cachear sólo miniaturas/tiles bajo demanda con LRU; fichas en tamaño medio | F1/F2 |
| 11 | Enumeraciones de condición (5) e idioma (5) frente a Cardmarket (más grados/idiomas) | Ampliarlas desde `/meta` según el export | F3/F7 |
| 12 | Semántica de "Low/Market/High" de la ficha frente a las columnas reales (`low`, `avg7`, `avg7_foil`, `low_foil`) | Mostrar `low / avg7 / avg7_foil` y tendencia 7/30 d | F2 |
| 13 | ¿Diseño ad hoc de Login/Admin/Landing a partir de tokens, o se encarga diseño nuevo? | Construir desde tokens y revisar con el usuario en cada PR | F1/F10/F11 |

---

*Fin del inventario. Las referencias `archivo:línea` apuntan al handoff original; los números de línea de `collection.py` apuntan al repo actual (`app/routes/domains/collection.py`).*
