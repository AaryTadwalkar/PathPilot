import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' })

export const metadata = {
  title: 'PathPilot — AI Learning Path Recommender',
  description: 'Personalized AI-powered learning paths tailored to your goals',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans antialiased bg-brand-bg text-brand-heading">{children}</body>
    </html>
  )
}
