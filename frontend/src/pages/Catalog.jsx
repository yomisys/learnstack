import {
  Box, Card, CardActionArea, CardContent, CardMedia, Chip, Container, Grid,
  Stack, Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useBranding } from '../branding'

export default function Catalog() {
  const [curricula, setCurricula] = useState([])
  const branding = useBranding()
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/api/learn/catalog').then((r) => setCurricula(r.data)).catch(() => {})
  }, [])

  return (
    <Box>
      <Box sx={{ bgcolor: 'secondary.main', color: 'secondary.contrastText', py: 8 }}>
        <Container>
          <Typography variant="h3" fontWeight={800}>{branding.product_name}</Typography>
          {branding.tagline && (
            <Typography variant="h6" sx={{ opacity: 0.85, mt: 1 }}>{branding.tagline}</Typography>
          )}
        </Container>
      </Box>
      <Container sx={{ py: 5 }}>
        <Typography variant="h5" fontWeight={700} gutterBottom>Courses</Typography>
        {curricula.length === 0 && (
          <Typography color="text.secondary">No published courses yet.</Typography>
        )}
        <Grid container spacing={3}>
          {curricula.map((c) => (
            <Grid item xs={12} sm={6} md={4} key={c.id}>
              <Card sx={{ height: '100%' }}>
                <CardActionArea sx={{ height: '100%' }} onClick={() => navigate(`/course/${c.id}`)}>
                  {c.cover_image_url && (
                    <CardMedia component="img" height="150" image={c.cover_image_url} alt="" />
                  )}
                  <CardContent>
                    <Typography variant="h6" fontWeight={600}>{c.title}</Typography>
                    <Typography variant="body2" color="text.secondary" sx={{
                      display: '-webkit-box', WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical', overflow: 'hidden', mb: 1,
                    }}>
                      {c.description}
                    </Typography>
                    <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                      <Chip size="small" label={c.language.toUpperCase()} />
                      {(c.tags || []).map((t) => <Chip key={t} size="small" variant="outlined" label={t} />)}
                    </Stack>
                  </CardContent>
                </CardActionArea>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Container>
    </Box>
  )
}
