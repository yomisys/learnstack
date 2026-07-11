import {
  Alert, Box, Button, Card, CardContent, Stack, Tab, Tabs, TextField, Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'
import { errText } from '../api'
import { useAuth } from '../auth'
import { useBranding } from '../branding'

export default function Login() {
  const { login, register } = useAuth()
  const branding = useBranding()
  const navigate = useNavigate()
  const [tab, setTab] = useState(0)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (tab === 0) await login(email, password)
      else await register(email, password, fullName)
      navigate('/')
    } catch (err) {
      setError(errText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box sx={{ maxWidth: 420, mx: 'auto', mt: 8, px: 2 }}>
      <Typography variant="h5" align="center" fontWeight={700} gutterBottom>
        {branding.product_name}
      </Typography>
      {branding.tagline && (
        <Typography align="center" color="text.secondary" gutterBottom>
          {branding.tagline}
        </Typography>
      )}
      <Card>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
          <Tab label="Sign in" />
          <Tab label="Create account" />
        </Tabs>
        <CardContent>
          <form onSubmit={submit}>
            <Stack spacing={2}>
              {tab === 1 && (
                <TextField label="Full name" value={fullName}
                  onChange={(e) => setFullName(e.target.value)} />
              )}
              <TextField label="Email" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} />
              <TextField label="Password" type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)}
                helperText={tab === 1 ? 'At least 8 characters' : undefined} />
              {error && <Alert severity="error">{error}</Alert>}
              <Button type="submit" variant="contained" size="large" disabled={busy}>
                {tab === 0 ? 'Sign in' : 'Create account'}
              </Button>
              <Typography variant="body2" align="center" color="text.secondary">
                Setting up for a church, school, or business?{' '}
                <RouterLink to="/signup">Create an organization</RouterLink>
              </Typography>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  )
}
