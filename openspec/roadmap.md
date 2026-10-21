# Roadmap — Rediseño Riftbound Manager (PWA)

> Documento maestro. Fuente: revisión del proyecto + handoff de diseño `Rift Manager.zip`
> (`design_handoff_riftbound_manager/`). Decisiones acordadas con el usuario el 2026-10-18.
> Cada fase se ejecuta como un cambio SDD en `openspec/changes/<fase>/`, con rama y PR propios.

## 1. Objetivo

- App **instalable en móvil** (PWA) y en escritorio.
- En escritorio la interfaz **no se estira**: cada módulo usa el espacio extra para mostrar más datos
  (más columnas, paneles laterales, layouts de 2–3 columnas).
- Recrear el diseño hifi del handoff (tokens, tipografía, componentes, interacciones) con datos reales.

## 2. Arquitectura objetivo

| Capa | Decisión |
|---|---|
| Backend | Flask se mantiene como **API JSON** en `/riftbound/api/v1/*`. Se reutilizan modelos, servicios (Cardmarket loader/matcher, Riot scraper), Pydantic y tests. |
| Frontend | Nuevo `frontend/`: **React + TypeScript + Vite** + `vite-plugin-pwa`, TanStack Query, React Router. |
| Auth | Cookie de sesión same-origin (Flask-Login) + CSRF. Sin JWT. |
| Migraciones | **Flask-Migrate (Alembic)** desde F0; baseline sobre el esquema actual. |
| Offline | **Solo lectura**: catálogo, colección y mazos consultables sin red. Las ediciones requieren conexión. |
| Despliegue | Nginx sirve el build en `/riftbound/` y proxy de `/riftbound/api` a Gunicorn. **HTTPS obligatorio** (certbot / Let's Encrypt). |
| Migración | **Convivencia gradual**: la PWA absorbe un módulo por PR; lo no migrado sigue en Jinja enlazado desde la app. |
| Precios | Solo **Cardmarket, EUR**. El selector de proveedor del diseño se oculta. |
| Idiomas | ES / EN reales. |

## 3. Reglas de juego (fuente única en backend, expuestas por API)

- 1 Leyenda · 1 Campeón elegido · **39 cartas de mazo principal** (40 contando el campeón).
- **12 runas** exactas, solo de los colores de la leyenda.
- **3 campos de batalla** distintos (no cuentan para el mazo).
- **Banquillo: 10 cartas** (el prototipo usaba 8 — obsoleto).
- Máx. **3 copias por nombre** (main + banquillo + taller + campeón elegido). Printings distintos = misma carta.
- Taller (workbench): hasta 100 cartas distintas, fuera del export.
- El campeón debe compartir tag con la leyenda; cambiar de leyenda purga runas y campeón incompatibles.
- **Baneos por modo** (`1v1`, `2v2`): una carta puede estar baneada en 1v1 y ser legal en 2v2.
  El baneo aplica al **nombre** (todas sus versiones). La UI indica en qué modo está baneada y
  marca el mazo como **no legal** para su modo, explicando el motivo.
- Los valores de las reglas viven en un único sitio del backend; el frontend los lee por API.

## 4. Usuarios y seguridad

- App **multiusuario**. Solo el propietario es **admin** (`is_admin`).
- Registro **abierto con protecciones**: límite de intentos en login/registro, CAPTCHA simple,
  bloqueo de cuentas desde Admin.
- Sin servidor de correo → no hay recuperación por email; el admin restablece contraseñas y
  existe login con Discord/Google como alternativa.
- Secretos solo por variables de entorno (hoy `config.py` trae credenciales por defecto).

## 5. Fases

| Fase | Contenido |
|---|---|
| **F0 Base** | Secretos a env, `is_admin` + decorador, proteger rutas admin actuales, Alembic baseline, `rbcol_quantity` → entero, CSRF, base API v1 con errores JSON, límite de intentos + CAPTCHA + bloqueo de cuenta, CI preparado para frontend, `AGENTS.md`/`README.md` al día, limpiar `package.json`. Integrar el fix pendiente (ver §7). |
| **F1 Estructura app** | Proyecto Vite + PWA (manifest, iconos, service worker), tokens de `riftbound.css`, fuentes autohospedadas (Manrope, Space Grotesk), fondo, i18n ES/EN, login/registro en React, topbar + bottom nav, preferencias de interfaz en BD (densidad, acento, intensidad de fondo, idioma, vista por defecto), componentes base, estados carga/vacío/error, Nginx + HTTPS. |
| **F2 Catálogo** | API de cartas con filtros y facetas, ficha de carta (modal) con histórico real de `rbcm_price`, mis copias, relacionadas, baneos por modo. Escritorio: filtros en panel lateral, más columnas. |
| **F3 Colección** | Tabla + grid, alta, edición en bloque, exportación, **asistente de importación CSV** (formato RBAPP, Cardmarket, riftdecks.com, piltoverarchive.com, otras apps — pedir ejemplos al usuario al llegar), wishlist, campo opcional **precio de compra** por línea. **Venta**: en cada línea se indica en bloque cuántas copias vender + interruptor para activarla; una flecha despliega las copias de una carta en sub-líneas con precio, estado e idioma distintos. Revisar cómo encaja el `rbcol_playset` actual. **Valores por defecto**: móvil compacto + cuadrícula, escritorio normal + tabla, acento naranja. |
| **F4 Precios + Dashboard** | Carga diaria automática de Cardmarket (timer), snapshot diario del valor de colección por usuario, cartas que más suben/bajan (7/30 d), lista de seguimiento con alertas **push**, KPIs + gráfico de 12 meses. |
| **F5 Mazos v2** | Formato v2 (leyenda, campeón, main, runas, campos, banquillo, taller), reglas en Python + TS con casos de test compartidos, **migración automática** de mazos existentes (por tipo de carta, conservando versiones), editor, import/export texto (incl. formatos riftdecks/piltover), legalidad por modo, mazo vs colección (faltantes + coste), diff de versiones, enlace público de solo lectura, simulador de mano inicial. **Visibilidad: privado por defecto**; el usuario puede marcar un mazo como público o generar enlace para compartir (hoy todos ven todos — se mantiene en F0). |
| **F6 Stats** | Distribución por dominio, rareza, tipo, set; top cartas por valor. |
| **F7 Sales** | Tabla de ventas, anuncios desde líneas en venta, vender descuenta inventario, **margen real si hay precio de compra; si no, comparación con mercado del día**, export compatible con Cardmarket. |
| **F8 Events** | Eventos manuales (**privado/público** a elegir) + importados del scraper (siempre públicos), guardados, resultado + mazo jugado, ICS, Google Calendar, recordatorios push. |
| **F9 Account** | Perfil ampliado + avatar, **2FA TOTP**, sesiones/dispositivos (tabla de sesiones en servidor), **login Discord/Google** (guiar al usuario paso a paso con las apps OAuth), API key. Sin pagos ni recuperación por email. |
| **F10 Admin** | Sets, edición de cartas, carga Cardmarket, mappings, ignorados, **usuarios** (bloquear, restablecer contraseña), **baneos por modo**. Pensado para escritorio. |
| **F11 Cierre** | Landing `/` con el estilo nuevo + botón instalar app, retirar Jinja, auditoría a11y, documentación final. |
| **F12 Paso a producción** | Hoy **no existe producción** (el servidor y la BD actuales son de desarrollo). Plan de despliegue, URL final, HTTPS, secretos de producción nuevos, BD de producción desde Alembic, backups, monitorización. |

## 6. Datos

- El catálogo (hasta Vendetta) ya lo mantiene el proceso de descarga de la galería oficial
  (`app/services/riot_scraper.py` → `rbcards`). El CSV del handoff **no** se importa.
- Imágenes: carpeta derivada del prefijo del fichero (`RbCard.image_src`).

## 7. Pendientes a integrar

- Fix `1ae1f6e` (rama `fix/promo-images-rune-foil-price-fallback`), presente en `main` local pero no
  en `origin/main`: carpeta de imagen por prefijo de fichero, Basic Rune sin foil, cadena de precios
  `avg7_foil → avg7 → low_foil → low`. Se conserva en la API nueva; viaja dentro de F0.

## 8. Dudas a pedir en su fase

- Ver también `openspec/design-handoff.md` §10 (13 decisiones abiertas del diseño, por fase).

- F1/despliegue: dominio y servidor para HTTPS.
- F3: ficheros CSV de ejemplo (riftdecks, piltoverarchive, otras apps).
- F9: creación de apps OAuth en Discord y Google (guía paso a paso).

## 9. Notas de plataforma

- Push en iOS solo con la PWA añadida a pantalla de inicio (iOS 16.4+).
- Empaquetado futuro en tiendas posible con Capacitor sin reescribir.
