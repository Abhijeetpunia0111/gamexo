export function shareOnWhatsApp(text: string, phone?: string) {
  // A 10-digit local number gets the country code prefixed so wa.me can route it;
  // with no number it falls back to WhatsApp's own contact picker.
  const to = phone && /^\d{10}$/.test(phone) ? `91${phone}` : ''
  window.open(`https://wa.me/${to}?text=${encodeURIComponent(text)}`, '_blank', 'noopener,noreferrer')
}

export function shareByEmail(subject: string, body: string, to = '') {
  window.location.href = `mailto:${to}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

export function shareBySms(text: string, phone?: string) {
  const to = phone && /^\d{10}$/.test(phone) ? phone : ''
  // `sms:` body param works on iOS/Android; desktop browsers simply ignore the scheme.
  window.location.href = `sms:${to}${to ? '?' : ''}&body=${encodeURIComponent(text)}`
}

/** The OS share sheet on a tablet/phone bundles WhatsApp, Mail, Messages, "copy link" etc.
 *  into one native picker — the best single button when it's available. */
export async function shareNative(data: { title: string; text: string; url?: string }) {
  if (!navigator.share) return false
  try {
    await navigator.share(data)
    return true
  } catch {
    // User dismissed the sheet — not an error worth surfacing.
    return false
  }
}

export async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}
