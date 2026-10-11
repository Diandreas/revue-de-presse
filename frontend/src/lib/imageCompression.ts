/**
 * Allègement des photos AVANT envoi.
 *
 * Une photo de téléphone pèse souvent 3 à 8 Mo ; sur une connexion mobile lente c'est
 * l'essentiel du temps d'attente. Le serveur ramène de toute façon chaque image à 2000 px
 * de côté avant de la faire lire par l'IA : envoyer davantage n'améliore pas la lecture.
 * On redimensionne donc à 2400 px max (marge de sécurité) en JPEG qualité 0.86.
 *
 * Sans risque : en cas d'échec (format non décodable par le navigateur comme le HEIC
 * hors Safari, mémoire insuffisante…) ou si le résultat n'est pas plus léger, on renvoie
 * le fichier d'origine tel quel — le serveur sait le traiter.
 */
const COMPRESSIBLE_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const MAX_EDGE = 2400
const JPEG_QUALITY = 0.86
const SMALL_ENOUGH_BYTES = 900 * 1024

function withJpegExtension(name: string) {
  const dot = name.lastIndexOf('.')
  return `${dot > 0 ? name.slice(0, dot) : name}.jpg`
}

export async function prepareImageForUpload(file: File): Promise<File> {
  if (!COMPRESSIBLE_TYPES.has(file.type) || typeof createImageBitmap !== 'function') return file
  let bitmap: ImageBitmap | null = null
  try {
    // `from-image` : respecte l'orientation EXIF (photo prise téléphone tourné).
    bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
    const longest = Math.max(bitmap.width, bitmap.height)
    if (longest <= MAX_EDGE && file.size <= SMALL_ENOUGH_BYTES) return file

    const scale = Math.min(1, MAX_EDGE / longest)
    const width = Math.max(1, Math.round(bitmap.width * scale))
    const height = Math.max(1, Math.round(bitmap.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (!context) return file
    context.fillStyle = '#ffffff' // fond blanc : la transparence d'un PNG deviendrait noire en JPEG
    context.fillRect(0, 0, width, height)
    context.imageSmoothingQuality = 'high'
    context.drawImage(bitmap, 0, 0, width, height)

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY))
    if (!blob || blob.size >= file.size) return file
    return new File([blob], withJpegExtension(file.name), { type: 'image/jpeg', lastModified: file.lastModified })
  } catch {
    return file
  } finally {
    bitmap?.close()
  }
}

// Mêmes formats que le serveur (backend/apps/core/uploads.py), qui vérifie de toute façon
// le contenu réel : un SVG, un GIF ou un TIFF est refusé dès la sélection.
const IMAGE_EXTENSIONS = /\.(jpe?g|png|webp|heic|heif)$/i
const IMAGE_TYPES = /^image\/(jpeg|png|webp|heic|heif)$/
const PDF_EXTENSION = /\.pdf$/i

export type LocalFileKind = 'pdf' | 'image' | 'unsupported'

export function classifyLocalFile(file: File): LocalFileKind {
  if (file.type === 'application/pdf' || PDF_EXTENSION.test(file.name)) return 'pdf'
  if (IMAGE_TYPES.test(file.type) || IMAGE_EXTENSIONS.test(file.name)) return 'image'
  return 'unsupported'
}

/** Les navigateurs (hors Safari) ne savent pas afficher le HEIC : pas d'aperçu, une icône. */
export function canPreviewInBrowser(file: File) {
  return /^image\/(jpeg|png|webp|gif|bmp)$/.test(file.type)
}
