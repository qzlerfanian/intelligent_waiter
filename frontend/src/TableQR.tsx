import { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import './tableQR.css'

export function TableQR({ url }: { url: string }) {
  const [image, setImage] = useState('')
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    QRCode.toDataURL(url, { width: 640, margin: 4, errorCorrectionLevel: 'M', color: { dark: '#183d34', light: '#ffffff' } }).then(value => { if (active) setImage(value) }).catch(() => { if (active) setError('ساخت تصویر QR ممکن نشد؛ لینک را ذخیره کنید.') })
    return () => { active = false }
  }, [url])
  return <div className="manage-qr-image">{image && <><img src={image} alt="QR منوی میز" width={256} height={256} /><a href={image} download="baran-table-qr.png">دانلود تصویر QR</a></>}{error && <p role="alert">{error}</p>}</div>
}
