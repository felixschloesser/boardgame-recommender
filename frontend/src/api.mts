import axios from 'axios'
import type BoardGame from './boardGame.mts'
import type { Option } from './boardGame.mjs'
import type { Recommendation } from './recommendation.mts'

const apiBaseUrl = 'http://127.0.0.1:8000/api'

type Participant = {
  participant_id: string
}

type Preferences = {
  liked_games: Option[]
  players: number
}

type ProblemDetails = {
  type?: string
  title?: string
  status?: number
  detail?: string
  instance?: string
  code?: string
  invalid_params?: { name: string; reason: string; code?: string }[]
}

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enables sending cookies and CORS support
})

/**
 * Sets up a session for a new participant.
 * @returns Participant id
 */
async function newParticipant(): Promise<Participant> {
  const participant: Participant = await apiClient
    .post('/auth/participant', {})
    .then((response) => {
      return response.data as Participant
    })
  console.log('Created participant:', participant.participant_id) // for debug purposes
  // Create a session for the participant
  await apiClient.post('/auth/session', {
    participant_id: participant.participant_id,
  })
  return participant
}

function getGames(query?: string): Promise<BoardGame[]> {
  return apiClient
    .get(`/games/`, { params: { q: query } })
    .then((response) => response.data.items as BoardGame[])
}

// Gets recommendations and returns the session id related to that recommendation
async function getRecommendations(preferences: Preferences): Promise<string> {
  const liked_game_ids = preferences.liked_games.map((game) => game.id)
  const response = await apiClient.post(`/recommendation`, {
    liked_games: liked_game_ids,
    play_context: { players: preferences.players },
  })
  return response.data.id as string
}

function getSessionRecommendations(session_id: string): Promise<Recommendation[]> {
  return apiClient
    .get(`/recommendation/${session_id}`)
    .then((response) => response.data.recommendations as Recommendation[])
}

// get added options from a session
async function getSessionPreferences(session_id: string): Promise<Preferences> {
  const response = await apiClient.get(`/recommendation/${session_id}`)
  const liked_game_ids = response.data.intent.liked_games as number[]
  const liked_games: Option[] = await Promise.all(
    liked_game_ids.map(async (id) => {
      const game = await apiClient.get(`/games/${id}`)
      return {
        id: game.data.id,
        name: game.data.title,
      } as Option
    }),
  )
  return {
    liked_games: liked_games,
    players: response.data.intent.play_context.players,
  }
}

export {
  newParticipant,
  getGames,
  getRecommendations,
  getSessionRecommendations,
  getSessionPreferences,
  formatApiError,
}
export type { Participant, Preferences, ProblemDetails }

function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status
    const data = error.response?.data as ProblemDetails | undefined
    const detail = data?.detail || data?.title
    if (detail) {
      return detail
    }
    if (status) {
      return `Request failed with status ${status}`
    }
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred. Please try again.'
}
