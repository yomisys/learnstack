import {
  Alert, Button, Card, CardContent, Container, Stack, TextField, Typography,
} from '@mui/material'
import { useState } from 'react'
import { api } from '../api'

export default function Verify() {
  const [code, setCode] = useState('')
  const [cert, setCert] = useState(null)
  const [error, setError] = useState('')

  const check = async (e) => {
    e.preventDefault()
    setCert(null)
    setError('')
    try {
      const r = await api.get(`/api/learn/certificates/verify/${code.trim()}`)
      setCert(r.data)
    } catch {
      setError('No certificate found for that code.')
    }
  }

  return (
    <Container sx={{ py: 6, maxWidth: 520 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>Verify a certificate</Typography>
      <form onSubmit={check}>
        <Stack direction="row" spacing={1}>
          <TextField fullWidth size="small" label="Certificate code" value={code}
            onChange={(e) => setCode(e.target.value)} />
          <Button type="submit" variant="contained">Verify</Button>
        </Stack>
      </form>
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      {cert && (
        <Card sx={{ mt: 3 }} variant="outlined">
          <CardContent>
            <Alert severity="success" sx={{ mb: 2 }}>Certificate is valid</Alert>
            <Typography><b>{cert.learner_name}</b> completed</Typography>
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
