import {
  Alert, Box, Button, Container, Divider, Grid, LinearProgress, Stack,
  TextField, Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useParams } from 'react-router-dom'
import { api, errText } from '../api'
import BlockEditor from '../components/BlockEditor'
import BlockRenderer from '../components/BlockRenderer'

export default function LessonEditor() {
  const { id } = useParams()
  const [lesson, setLesson] = useState(null)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api.get(`/api/content/lessons/${id}`)
      .then((r) => setLesson(r.data))
      .catch((e) => setError(errText(e)))
  }, [id])

  if (error && !lesson) return <Container sx={{ py: 4 }}><Alert severity="error">{error}</Alert></Container>
  if (!lesson) return <Container sx={{ py: 4 }}><LinearProgress /></Container>

  const save = async () => {
    setError('')
    setSaved(false)
    try {
      const { title, summary, sort_order, duration_minutes, blocks } = lesson
      await api.put(`/api/content/lessons/${id}`,
        { title, summary, sort_order, duration_minutes, blocks })
      setSaved(true)
    } catch (e) {
      setError(errText(e))
    }
  }

  return (
    <Container sx={{ py: 4 }}>
      <Button component={Link} to="/admin" size="small">← Studio</Button>
      <Typography variant="h4" fontWeight={700} sx={{ mt: 1, mb: 3 }}>Edit lesson</Typography>
      <Grid container spacing={4}>
        <Grid item xs={12} md={6}>
          <Stack spacing={2}>
            <TextField label="Title" value={lesson.title}
              onChange={(e) => setLesson({ ...lesson, title: e.target.value })} />
            <TextField label="Summary" multiline minRows={2} value={lesson.summary}
              onChange={(e) => setLesson({ ...lesson, summary: e.target.value })} />
            <TextField label="Duration (minutes)" type="number" sx={{ width: 200 }}
              value={lesson.duration_minutes}
              onChange={(e) => setLesson({ ...lesson, duration_minutes: Number(e.target.value) })} />
            <Divider>Content blocks</Divider>
            <BlockEditor blocks={lesson.blocks}
              onChange={(blocks) => setLesson({ ...lesson, blocks })} />
            {error && <Alert severity="error">{error}</Alert>}
            {saved && <Alert severity="success">Lesson saved.</Alert>}
            <Button variant="contained" size="large" onClick={save}>Save lesson</Button>
          </Stack>
        </Grid>
        <Grid item xs={12} md={6}>
          <Typography variant="overline" color="text.secondary">Live preview</Typography>
          <Box sx={{ border: '1px dashed', borderColor: 'divider', borderRadius: 2, p: 2 }}>
            <Typography variant="h5" fontWeight={700} gutterBottom>{lesson.title}</Typography>
            <Stack spacing={2}>
              {lesson.blocks.map((b, i) => (
                <BlockRenderer key={i} block={b} index={i} lessonId={lesson.id} />
              ))}
            </Stack>
          </Box>
        </Grid>
      </Grid>
    </Container>
  )
}
