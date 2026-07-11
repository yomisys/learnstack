import {
  Alert, Button, Card, CardContent, Container, Stack, TextField, Typography,
} from '@mui/material'
import { useState } from 'react'
import { api } from '../api'

export default function Verify() {
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [checkedName, setCheckedName] = useState('')
  const [cert, setCert] = useState(null)
  const [error, setError] = useState('')

  const check = async (e) => {
    e.preventDefault()
    setCert(null)
    setError('')
    try {
      const r = await api.get(`/api/learn/certificates/verify/${encodeURIComponent(code.trim())}`, {
        params: { name: name.trim() },
      })
      setCert(r.data)
      setCheckedName(name.trim())
    } catch {
      setError('No certificate found for that code and name.')
    }
  }

  return (
    <Container sx={{ py: 6, maxWidth: 520 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>Verify a certificate</Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Enter both the certificate code and the full name it was issued to.
      </Typography>
      <form onSubmit={check}>
        <Stack spacing={2}>
          <TextField fullWidth size="small" label="Certificate code" value={code}
            onChange={(e) => setCode(e.target.value)} />
          <TextField fullWidth size="small" label="Full name" value={name}
            onChange={(e) => setName(e.target.value)} />
          <Button type="submit" variant="contained" disabled={!code.trim() || !name.trim()}>
            Verify
          </Button>
        </Stack>
      </form>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {cert && (
        <Card sx={{ mt: 3 }} variant="outlined">
          <CardContent>
            <Alert severity="success" sx={{ mb: 2 }}>Certificate is valid</Alert>
            <Typography><b>{checkedName}</b> completed</Typography>
            <Typography variant="h6" fontWeight={700}>{cert.curriculum_title}</Typography>
            <Typography color="text.secondary">
              Issued by {cert.tenant_name} on {new Date(cert.issued_at).toLocaleDateString()}
            </Typography>
          </CardContent>
        </Card>
      )}
    </Container>
  )
}
