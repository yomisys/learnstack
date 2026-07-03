import SendIcon from '@mui/icons-material/Send'
import {
  Alert, Box, Button, Card, CardContent, Chip, Container, FormControlLabel,
  Grid, IconButton, MenuItem, Stack, Switch, TextField, Typography,
} from '@mui/material'
import { useEffect, useRef, useState } from 'react'
import { api, errText } from '../api'

const PROVIDERS = {
  whatsapp: ['simulator', 'meta'],
  sms: ['simulator', 'africastalking', 'twilio'],
  ussd: ['simulator', 'africastalking'],
}
const CRED_FIELDS = {
  meta: ['phone_number_id', 'access_token', 'verify_token'],
  africastalking: ['username', 'api_key', 'sender_id'],
  twilio: ['account_sid', 'auth_token', 'from_number'],
  simulator: [],
}

function ChannelCard({ config, onSaved }) {
  const [provider, setProvider] = useState(config.provider || 'simulator')
  const [creds, setCreds] = useState(config.credentials || {})
  const [active, setActive] = useState(config.is_active)
  const [msg, setMsg] = useState('')

  const save = async () => {
    setMsg('')
    try {
      await api.put(`/api/channels/config/${config.channel}`, {
        provider, credentials: creds, is_active: active,
      })
      setMsg('Saved')
      onSaved?.()
    } catch (e) {
      setMsg(errText(e))
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6" fontWeight={700} textTransform="uppercase">
            {config.channel}
          </Typography>
          <FormControlLabel
            control={<Switch checked={active} onChange={(e) => setActive(e.target.checked)} />}
            label="Enabled"
          />
        </Stack>
        <Stack spacing={1.5} sx={{ mt: 1 }}>
          <TextField select size="small" label="Provider" value={provider}
            onChange={(e) => setProvider(e.target.value)}>
            {PROVIDERS[config.channel].map((p) => (
              <MenuItem key={p} value={p}>{p}</MenuItem>
            ))}
          </TextField>
          {CRED_FIELDS[provider].map((field) => (
            <TextField key={field} size="small" label={field} value={creds[field] || ''}
              type={/token|key|secret/.test(field) ? 'password' : 'text'}
              onChange={(e) => setCreds({ ...creds, [field]: e.target.value })} />
          ))}
          <Typography variant="caption" color="text.secondary" sx={{ wordBreak: 'break-all' }}>
            Webhook: {config.webhook_path}
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Button variant="contained" size="small" onClick={save}>Save</Button>
            {msg && <Typography variant="caption" color="text.secondary">{msg}</Typography>}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  )
}

function Simulator() {
  const [channel, setChannel] = useState('whatsapp')
  const [address, setAddress] = useState('+2348000000001')
  const [input, setInput] = useState('hi')
  const [log, setLog] = useState([])
  const [error, setError] = useState('')
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [log])

  const send = async () => {
    if (!input.trim()) return
    const outgoing = input
    setInput('')
    setError('')
    setLog((l) => [...l, { dir: 'out', type: 'text', body: outgoing }])
    try {
      const r = await api.post('/api/channels/simulate', {
        channel, address, message: outgoing,
      })
      setLog((l) => [...l, ...r.data.replies.map((m) => ({ dir: 'in', ...m }))])
    } catch (e) {
      setError(errText(e))
    }
  }

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ display: 'flex', flexDirection: 'column', height: 560 }}>
        <Typography variant="h6" fontWeight={700} gutterBottom>
          Conversation simulator
        </Typography>
        <Stack direction="row" spacing={1} sx={{ mb: 1 }}>
          <TextField select size="small" label="Channel" value={channel} sx={{ width: 140 }}
            onChange={(e) => { setChannel(e.target.value); setLog([]) }}>
            {Object.keys(PROVIDERS).map((c) => <MenuItem key={c} value={c}>{c}</MenuItem>)}
          </TextField>
          <TextField size="small" label="Phone number" value={address} fullWidth
            onChange={(e) => setAddress(e.target.value)} />
        </Stack>
        <Box sx={{
          flexGrow: 1, overflowY: 'auto', bgcolor: 'grey.100',
          borderRadius: 2, p: 1.5, mb: 1,
        }}>
          {log.length === 0 && (
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 4 }}>
              Send "hi" to start a conversation, exactly as a learner would on {channel}.
            </Typography>
          )}
          {log.map((m, i) => (
            <Box key={i} sx={{
              display: 'flex',
              justifyContent: m.dir === 'out' ? 'flex-end' : 'flex-start', mb: 0.75,
            }}>
              <Box sx={{
                maxWidth: '85%', px: 1.5, py: 0.75, borderRadius: 2,
                bgcolor: m.dir === 'out' ? 'primary.main' : 'background.paper',
                color: m.dir === 'out' ? 'primary.contrastText' : 'text.primary',
                boxShadow: 1, whiteSpace: 'pre-wrap', fontSize: 14,
              }}>
                {m.type === 'text' ? m.body : (
                  <Stack spacing={0.5}>
                    <Chip size="small" label={m.type} color="secondary" sx={{ width: 'fit-content' }} />
                    {m.caption && <span>{m.caption}</span>}
                    <Typography variant="caption" sx={{ wordBreak: 'break-all' }}>{m.url}</Typography>
                  </Stack>
                )}
              </Box>
            </Box>
          ))}
          <div ref={bottomRef} />
        </Box>
        {error && <Alert severity="error" sx={{ mb: 1 }}>{error}</Alert>}
        <Stack direction="row" spacing={1}>
          <TextField size="small" fullWidth placeholder="Type a message…" value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()} />
          <IconButton color="primary" onClick={send}><SendIcon /></IconButton>
        </Stack>
      </CardContent>
    </Card>
  )
}

export default function Channels() {
  const [configs, setConfigs] = useState([])
  const load = () => api.get('/api/channels/config').then((r) => setConfigs(r.data)).catch(() => {})
  useEffect(() => { load() }, [])

  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>Messaging channels</Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        Deliver your curricula over WhatsApp (with real video, audio, and image
        messages), SMS, and USSD for feature phones. Test any flow in the
        simulator before connecting a provider.
      </Typography>
      <Grid container spacing={3}>
        <Grid item xs={12} md={5}>
          <Stack spacing={2}>
            {configs.map((c) => <ChannelCard key={c.channel} config={c} onSaved={load} />)}
          </Stack>
        </Grid>
        <Grid item xs={12} md={7}>
          <Simulator />
        </Grid>
      </Grid>
    </Container>
  )
}
