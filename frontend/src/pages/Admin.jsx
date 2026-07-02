import AddIcon from '@mui/icons-material/Add'
import {
  Alert, Box, Button, Card, CardContent, Chip, Container, Dialog,
  DialogActions, DialogContent, DialogTitle, Grid, Stack, TextField,
  Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, errText } from '../api'

function BrandingCard() {
  const [branding, setBranding] = useState(null)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.get('/api/tenants/branding').then((r) => setBranding(r.data.branding)).catch(() => {})
  }, [])

  if (!branding) return null
  const set = (k) => (e) => setBranding({ ...branding, [k]: e.target.value })

  const save = async () => {
    setMsg('')
    try {
      await api.patch('/api/tenants/current', { branding })
      setMsg('Saved — reload to see the new theme.')
    } catch (e) {
      setMsg(errText(e))
    }
  }

  return (
    <Card variant="outlined" sx={{ mb: 4 }}>
      <CardContent>
        <Typography variant="h6" fontWeight={700} gutterBottom>White-label branding</Typography>
        <Grid container spacing={2}>
          {[
            ['product_name', 'Product name'], ['tagline', 'Tagline'],
            ['logo_url', 'Logo URL'], ['favicon_url', 'Favicon URL'],
            ['primary_color', 'Primary color (hex)'], ['secondary_color', 'Secondary color (hex)'],
            ['support_email', 'Support email'], ['footer_text', 'Footer text'],
          ].map(([key, label]) => (
            <Grid item xs={12} sm={6} key={key}>
              <TextField fullWidth size="small" label={label}
                value={branding[key] || ''} onChange={set(key)} />
            </Grid>
          ))}
        </Grid>
        <Stack direction="row" spacing={2} alignItems="center" sx={{ mt: 2 }}>
          <Button variant="contained" onClick={save}>Save branding</Button>
          {msg && <Typography variant="body2" color="text.secondary">{msg}</Typography>}
        </Stack>
      </CardContent>
    </Card>
  )
}

export default function Admin() {
  const [curricula, setCurricula] = useState([])
  const [open, setOpen] = useState(false)
  const [form, setForm] = useState({ slug: '', title: '', description: '' })
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = useCallback(() => {
    api.get('/api/content/curricula').then((r) => setCurricula(r.data)).catch((e) => setError(errText(e)))
  }, [])
  useEffect(() => { load() }, [load])

  const create = async () => {
    setError('')
    try {
      const r = await api.post('/api/content/curricula', form)
      setOpen(false)
      navigate(`/admin/curriculum/${r.data.id}`)
    } catch (e) {
      setError(errText(e))
    }
  }

  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>Studio</Typography>
      <BrandingCard />

      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>Curricula</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
          New curriculum
        </Button>
      </Stack>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Grid container spacing={2}>
        {curricula.map((c) => (
          <Grid item xs={12} sm={6} md={4} key={c.id}>
            <Card sx={{ cursor: 'pointer' }} onClick={() => navigate(`/admin/curriculum/${c.id}`)}>
              <CardContent>
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Typography variant="h6" fontWeight={600}>{c.title}</Typography>
                  <Chip size="small" label={c.status}
                    color={c.status === 'published' ? 'success' : 'default'} />
                </Stack>
                <Typography variant="body2" color="text.secondary">/{c.slug}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Dialog open={open} onClose={() => setOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>New curriculum</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField label="Title" value={form.title}
              onChange={(e) => setForm({
                ...form, title: e.target.value,
                slug: e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
              })} />
            <TextField label="Slug" value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
              helperText="Lowercase letters, numbers, dashes" />
            <TextField label="Description" multiline minRows={2} value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={create} disabled={!form.title || !form.slug}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  )
}
