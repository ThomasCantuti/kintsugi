import '@fontsource/shippori-mincho-b1/latin-500.css'
import '@fontsource/shippori-mincho-b1/latin-700.css'
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import './styles.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { start } from './live'

start()
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
