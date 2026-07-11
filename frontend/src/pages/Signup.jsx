import {
  Alert, Box, Button, Card, CardContent, Stack, TextField, Typography,
} from '@mui/material'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'
import { errText } from '../api'
import { useAuth } from '../auth'

const slugify = (s) => s.toLowerCase().trim()
  .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 59)

export default function Signup() {
  const { signupOrg } = useAuth()
  const [orgName, setOrgName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await signupOrg({
        slug, org_name: orgName, admin_full_name: fullName,
        admin_email: email, admin_password: password,
      })
      // Hard navigation: api.js binds TENANT from localStorage at module
      // load, so a client-side route change would keep sending requests
      // under the old (default) tenant.
      localStorage.setItem('tenant', slug)
      window.location.href = `/admin?tenant=${slug}`
    } catch (err) {
      setError(errText(err))
      setBusy(false)
    }
  }

  return (
    <Box sx={{ maxWidth: 460, mx: 'auto', mt: 8, px: 2 }}>
      <Typography variant="h5" align="center" fontWeight={700} gutterBottom>
        Create your organization
      </Typography>
      <Typography align="center" color="text.secondary" sx={{ mb: 3 }}>
        For a church, school, business, or community group that wants to run
        its own branded courses.
      </Typography>
      <Card>
        <CardContent>
          <form onSubmit={submit}>
            <Stack spacing={2}>
              <TextField label="Organization name" required value={orgName}
                onChange={(e) => {
                  setOrgName(e.target.value)
                  if (!slugEdited) setSlug(slugify(e.target.value))
                }} />
              <TextField label="Organization URL" required value={slug}
                onChange={(e) => { setSlugEdited(true); setSlug(slugify(e.target.value)) }}
                helperText={slug ? `Your learners will sign in via ?tenant=${slug}` : 'Lowercase letters, numbers, dashes'} />
              <TextField label="Your full name" required value={fullName}
                onChange={(e) => setFullName(e.target.value)} />
              <TextField label="Your email" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} />
              <TextField label="Password" type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)}
                helperText="At least 8 characters" />
              {error && <Alert severity="error">{error}</Alert>}
              <Button type="submit" variant="contained" size="large" disabled={busy}>
                Create organization
              </Button>
              <Typography variant="body2" align="center" color="text.secondary">
                Already have an organization?{' '}
                <RouterLink to="/login">Sign in</RouterLink>
              </Typography>
            </Stack>
          </form>
        </CardContent>
      </Card>
    </Box>
  )
}
