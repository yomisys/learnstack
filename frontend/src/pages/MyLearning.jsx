import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium'
import {
  Box, Card, CardActionArea, CardContent, Container, Grid, LinearProgress,
  Stack, Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function MyLearning() {
  const [enrollments, setEnrollments] = useState([])
  const [certs, setCerts] = useState([])
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/api/learn/enrollments').then((r) => setEnrollments(r.data)).catch(() => {})
    api.get('/api/learn/certificates').then((r) => setCerts(r.data)).catch(() => {})
  }, [])

  return (
    <Container sx={{ py: 4 }}>
      <Typography variant="h4" fontWeight={700} gutterBottom>My learning</Typography>
      {enrollments.length === 0 && (
        <Typography color="text.secondary">You haven't enrolled in any course yet.</Typography>
      )}
      <Grid container spacing={2}>
        {enrollments.map((e) => (
          <Grid item xs={12} sm={6} md={4} key={e.id}>
            <Card>
              <CardActionArea onClick={() => navigate(`/course/${e.curriculum.id}`)}>
                <CardContent>
                  <Typography variant="h6" fontWeight={600}>{e.curriculum.title}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {e.completed_at ? 'Completed' : `${e.progress.length} lessons done`}
                  </Typography>
                </CardContent>
              </CardActionArea>
            </Card>
          </Grid>
        ))}
      </Grid>

      {certs.length > 0 && (
        <Box sx={{ mt: 5 }}>
          <Typography variant="h5" fontWeight={700} gutterBottom>Certificates</Typography>
          <Stack spacing={2}>
            {certs.map((c) => (
              <Card key={c.code} variant="outlined">
                <CardContent>
                  <Stack direction="row" spacing={2} alignItems="center">
                    <WorkspacePremiumIcon color="primary" sx={{ fontSize: 44 }} />
                    <Box>
                      <Typography fontWeight={700}>{c.curriculum_title}</Typography>
                      <Typography variant="body2" color="text.secondary">
                        Awarded to {c.learner_name} by {c.tenant_name} ·{' '}
                        {new Date(c.issued_at).toLocaleDateString()}
                      </Typography>
                      <Typography variant="body2">
                        Verification code: <b>{c.code}</b>
                      </Typography>
                    </Box>
                  </Stack>
                </CardContent>
              </Card>
            ))}
          </Stack>
        </Box>
      )}
    </Container>
  )
}
