import { useEffect, useState } from 'react'
import Lottie from 'lottie-react'

export default function SuccessGraphic({ className = '' }: { className?: string }) {
  const [animationData, setAnimationData] = useState<object | null>(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}checkin-success.json`)
      .then((res) => res.json())
      .then(setAnimationData)
  }, [])

  if (!animationData) return <div className={className} aria-hidden="true" />

  return <Lottie animationData={animationData} loop={false} className={className} aria-hidden="true" />
}
