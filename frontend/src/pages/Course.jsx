import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'
import {
  Alert, Box, Button, Chip, Container, LinearProgress, List, ListItemButton,
  ListItemIcon, ListItemText, Stack, Typography,
} from '@mui/material'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, errText } from '../api'
import { useAuth } from '../auth'

export default function Course() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [course, setCourse] = useState(null)
  const [enrollment, setEnrollment] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const r = await api.get(`/api/learn/curricula/${id}`)
      setCourse(r.data)
      if (user) {
        const enr = await api.get('/api/learn/enrollments')
        setEnrollment(enr.data.find((e) => e.curriculum.id === Number(id)) || null)
      }
    } catch (e) {
      setError(errText(e))
    }
  }, [id, user])

  useEffect(() => { load() }, [load])

  const enroll = async () => {
    if (!user) return navigate('/login')
    try {
      await api.post(`/api/learn/curricula/${id}/enroll`)
      await load()
    } catch (e) {
      setError(errText(e))
    }
  }

  if (error) return <Container sx={{ py: 4 }}><Alert severity="error">{error}</Alert></Container>
  if (!course) return <Container sx={{ py: 4 }}><LinearProgress /></Container>

  const doneIds = new Set((enrollment?.progress || []).map((p) => p.lesson_id))
  const totalLessons = course.modules.reduce((n, m) => n + m.lessons.length, 0)
  const pct = totalLessons ? Math.round((doneIds.size / totalLessons) * 100) : 0

  return (
    <Container sx={{ py: 4, maxWidth: 900 }}>
      <Typography variant="h4" fontWeight={700}>{course.title}</Typography>
      <Stack direction="row" spacing={1} sx={{ my: 1 }}>
        <Chip size="small" label={course.language.toUpperCase()} />
        {(course.tags || []).map((t) => <Chip key={t} size="small" variant="outlined" label={t} />)}
      </Stack>
      <Typography color="text.secondary" sx={{ mb: 3, whiteSpace: 'pre-wrap' }}>
        {course.description}
      </Typography>

      {enrollment ? (
        <Box sx={{ mb: 3 }}>
          <Stack direction="row" justifyContent="space-between">
            <Typography variant="body2">Progress: {doneIds.size}/{totalLessons} lessons</Typography>
            <Typography variant="body2" fontWeight={600}>{pct}%</Typography>
          </Stack>
          <LinearProgress variant="determinate" value={pct} sx={{ height: 8, borderRadius: 4 }} />
          {enrollment.completed_at && (
            <Alert severity="success" sx={{ mt: 2 }}>
              Course completed — your certificate is in <b>My learning</b>.
            </Alert>
          )}
        </Box>
      ) : (
        <Button variant="contained" size="large" onClick={enroll} sx={{ mb: 3 }}>
          {user ? 'Enroll now — free' : 'Sign in to enroll'}
        </Button>
      )}

      {course.modules.map((m) => (
        <Box key={m.id} sx={{ mb: 2 }}>
          <Typography variant="h6" fontWeight={600}>{m.title}</Typography>
          {m.description && <Typography variant="body2" color="text.secondary">{m.description}</Typography>}
          <List dense>
            {m.lessons.map((l) => (
              <ListItemButton
                key={l.id}
                disabled={!enrollment}
                onClick={() => navigate(`/lesson/${l.id}`)}
              >
                <ListItemIcon>
                  {doneIds.has(l.id)
                    ? <CheckCircleIcon color="success" />
                    : <PlayCircleOutlineIcon color="action" />}
                </ListItemIcon>
                <ListItemText
                  primary={l.title}
                  secondary={l.duration_minutes ? `${l.duration_minutes} min` : null}
                />
              </ListItemButton>
            ))}
          </List>
        </Box>
      ))}
    </Container>
  )
}
