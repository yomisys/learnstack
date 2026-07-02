import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import {
  Alert, Box, Button, Card, CardContent, Chip, Container, IconButton,
  LinearProgress, List, ListItem, ListItemButton, ListItemText, Stack,
  TextField, Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, errText } from '../api'

export default function CurriculumEditor() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [cur, setCur] = useState(null)
  const [error, setError] = useState('')
  const [newModule, setNewModule] = useState('')
  const [newLesson, setNewLesson] = useState({})

  const load = useCallback(() => {
    api.get(`/api/content/curricula/${id}`)
      .then((r) => setCur(r.data))
      .catch((e) => setError(errText(e)))
  }, [id])
  useEffect(() => { load() }, [load])

  if (error) return <Container sx={{ py: 4 }}><Alert severity="error">{error}</Alert></Container>
  if (!cur) return <Container sx={{ py: 4 }}><LinearProgress /></Container>

  const act = async (fn) => {
    setError('')
    try { await fn(); await load() } catch (e) { setError(errText(e)) }
  }

  const togglePublish = () => act(() =>
    api.patch(`/api/content/curricula/${id}`, {
      status: cur.status === 'published' ? 'draft' : 'published',
    }))

  const addModule = () => act(async () => {
    await api.post(`/api/content/curricula/${id}/modules`, {
      title: newModule, sort_order: cur.modules.length,
    })
    setNewModule('')
  })

  const addLesson = (moduleId, count) => act(async () => {
    const r = await api.post(`/api/content/modules/${moduleId}/lessons`, {
      title: newLesson[moduleId], sort_order: count,
    })
    setNewLesson({ ...newLesson, [moduleId]: '' })
    navigate(`/admin/lesson/${r.data.id}`)
  })

  return (
    <Container sx={{ py: 4, maxWidth: 900 }}>
      <Button component={Link} to="/admin" size="small">← Studio</Button>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mt: 1, mb: 2 }}>
        <Box>
          <Typography variant="h4" fontWeight={700}>{cur.title}</Typography>
          <Chip size="small" sx={{ mt: 1 }} label={cur.status}
            color={cur.status === 'published' ? 'success' : 'default'} />
        </Box>
        <Stack direction="row" spacing={1}>
          <Button variant="outlined" color="error"
            onClick={() => {
              if (window.confirm('Delete this curriculum and all its content?')) {
                act(async () => {
                  await api.delete(`/api/content/curricula/${id}`)
                  navigate('/admin')
                })
              }
            }}>
            Delete
          </Button>
          <Button variant="contained" onClick={togglePublish}>
            {cur.status === 'published' ? 'Unpublish' : 'Publish'}
          </Button>
        </Stack>
      </Stack>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {cur.modules.map((m) => (
        <Card key={m.id} variant="outlined" sx={{ mb: 2 }}>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6" fontWeight={600}>{m.title}</Typography>
              <IconButton
                onClick={() => act(() => api.delete(`/api/content/modules/${m.id}`))}>
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Stack>
            <List dense>
              {m.lessons.map((l) => (
                <ListItem key={l.id} disablePadding secondaryAction={
                  <IconButton edge="end"
                    onClick={() => act(() => api.delete(`/api/content/lessons/${l.id}`))}>
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                }>
                  <ListItemButton onClick={() => navigate(`/admin/lesson/${l.id}`)}>
                    <EditIcon fontSize="small" sx={{ mr: 1, color: 'text.secondary' }} />
                    <ListItemText primary={l.title}
                      secondary={`${(l.blocks || []).length} blocks`} />
                  </ListItemButton>
                </ListItem>
              ))}
            </List>
            <Stack direction="row" spacing={1}>
              <TextField size="small" fullWidth placeholder="New lesson title"
                value={newLesson[m.id] || ''}
                onChange={(e) => setNewLesson({ ...newLesson, [m.id]: e.target.value })} />
              <Button startIcon={<AddIcon />} disabled={!newLesson[m.id]}
                onClick={() => addLesson(m.id, m.lessons.length)}>
                Lesson
              </Button>
            </Stack>
          </CardContent>
        </Card>
      ))}

      <Stack direction="row" spacing={1} sx={{ mt: 2 }}>
        <TextField size="small" fullWidth placeholder="New module title"
          value={newModule} onChange={(e) => setNewModule(e.target.value)} />
        <Button variant="outlined" startIcon={<AddIcon />} disabled={!newModule}
          onClick={addModule}>
          Module
        </Button>
      </Stack>
    </Container>
  )
}
