import { CssBaseline, ThemeProvider, createTheme } from '@mui/material'
import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './api'

const BrandingContext = createContext(null)
export const useBranding = () => useContext(BrandingContext)

const FALLBACK = {
  product_name: 'LearnStack',
  tagline: '',
  logo_url: '',
  primary_color: '#1a7f5a',
  secondary_color: '#12325c',
  footer_text: '',
}

export function BrandingProvider({ children }) {
  const [branding, setBranding] = useState(FALLBACK)
  const [tenantName, setTenantName] = useState('')

  useEffect(() => {
    api
      .get('/api/tenants/branding')
      .then((r) => {
        setBranding({ ...FALLBACK, ...r.data.branding })
        setTenantName(r.data.name)
        document.title = r.data.branding.product_name || r.data.name
        if (r.data.branding.favicon_url) {
          const link =
            document.querySelector("link[rel='icon']") ||
            Object.assign(document.createElement('link'), { rel: 'icon' })
          link.href = r.data.branding.favicon_url
          document.head.appendChild(link)
        }
      })
      .catch(() => document.title = FALLBACK.product_name)
  }, [])

  const theme = useMemo(
    () =>
      createTheme({
        palette: {
          primary: { main: branding.primary_color || FALLBACK.primary_color },
          secondary: { main: branding.secondary_color || FALLBACK.secondary_color },
        },
        shape: { borderRadius: 10 },
      }),
    [branding],
  )

  return (
    <BrandingContext.Provider value={{ ...branding, tenantName }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </BrandingContext.Provider>
  )
}
