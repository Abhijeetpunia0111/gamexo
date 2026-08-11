/**
 * Thin wrapper around Google's free "Website Translator" widget (translate.google.com),
 * driven headlessly — we render our own dropdown in TopBar and just puppet Google's
 * hidden <select> to switch languages, instead of showing its default UI.
 *
 * No API key / billing involved; this is the same script consumer sites have embedded
 * for years, not the paid Cloud Translation API.
 */

export type LangCode = 'en' | 'hi' | 'te'

export const LANGUAGES: { code: LangCode; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'te', label: 'తెలుగు' },
]

const STORAGE_KEY = 'gamexo-pos-lang'
const CONTAINER_ID = 'google_translate_element'

declare global {
  interface Window {
    google?: { translate?: { TranslateElement?: new (options: unknown, containerId: string) => unknown } }
    googleTranslateElementInit?: () => void
  }
}

export function getStoredLanguage(): LangCode {
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored === 'hi' || stored === 'te' ? stored : 'en'
}

let loadPromise: Promise<void> | null = null

/** Injects the widget script once and constructs it into a hidden container.
 *  Safe to call from every TopBar instance — later calls just reuse the same promise. */
export function loadGoogleTranslate(): Promise<void> {
  if (loadPromise) return loadPromise

  loadPromise = new Promise((resolve) => {
    if (!document.getElementById(CONTAINER_ID)) {
      const el = document.createElement('div')
      el.id = CONTAINER_ID
      el.className = 'notranslate'
      // Off-screen, not zero-size/display:none — the widget skips building its interactive
      // <select> for elements it detects as unrendered.
      el.style.cssText = 'position:fixed;top:-9999px;left:-9999px;'
      document.body.appendChild(el)
    }

    window.googleTranslateElementInit = () => {
      new window.google!.translate!.TranslateElement!(
        { pageLanguage: 'en', includedLanguages: 'en,hi,te', autoDisplay: false },
        CONTAINER_ID,
      )
      resolve()
    }

    if (document.getElementById('google-translate-script')) return
    const script = document.createElement('script')
    script.id = 'google-translate-script'
    script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit'
    script.async = true
    document.body.appendChild(script)
  })

  return loadPromise
}

/** The widget builds its <select> asynchronously after the script loads — poll briefly
 *  rather than assume it exists the moment `loadGoogleTranslate` resolves. */
function findCombo(timeoutMs = 4000): Promise<HTMLSelectElement | null> {
  return new Promise((resolve) => {
    const existing = document.querySelector<HTMLSelectElement>('select.goog-te-combo')
    if (existing) return resolve(existing)

    const start = Date.now()
    const timer = setInterval(() => {
      const combo = document.querySelector<HTMLSelectElement>('select.goog-te-combo')
      if (combo || Date.now() - start > timeoutMs) {
        clearInterval(timer)
        resolve(combo)
      }
    }, 150)
  })
}

/** Switches the live page to `lang` (or back to the original English with 'en'). */
export async function setLanguage(lang: LangCode): Promise<void> {
  localStorage.setItem(STORAGE_KEY, lang)
  await loadGoogleTranslate()
  const combo = await findCombo()
  if (!combo) {
    console.warn('Google Translate <select> never appeared — language not switched.')
    return
  }
  combo.value = lang
  combo.dispatchEvent(new Event('change', { bubbles: true }))
}

/**
 * Google's translate widget rewrites text nodes in place, which occasionally leaves a
 * node detached from where React's reconciler still thinks it lives — the classic
 * "Failed to execute 'removeChild'/'insertBefore' on 'Node'" crash reported against
 * every React + Google Translate combination. Patched once, defensively, at import time:
 * fall back to a no-op instead of throwing when the node has already moved.
 */
let patched = false
export function patchDomForTranslateWidget() {
  if (patched) return
  patched = true

  const removeChild = Node.prototype.removeChild
  // @ts-expect-error - intentionally loosening the signature to guard a runtime-only edge case
  Node.prototype.removeChild = function (child) {
    if (child.parentNode !== this) {
      if (console) console.warn('Skipped a removeChild call for a node already moved by Google Translate.')
      return child
    }
    return removeChild.apply(this, arguments as never)
  }

  const insertBefore = Node.prototype.insertBefore
  // @ts-expect-error - same guard, for insertBefore
  Node.prototype.insertBefore = function (newNode, referenceNode) {
    if (referenceNode && referenceNode.parentNode !== this) {
      if (console) console.warn('Skipped an insertBefore call for a reference node already moved by Google Translate.')
      return newNode
    }
    return insertBefore.apply(this, arguments as never)
  }
}
