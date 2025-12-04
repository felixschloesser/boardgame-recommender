import axios from 'axios'
import type BoardGame from './boardGame.mts'
import type { Recommendation } from './recommendation.mts'

const apiBaseUrl = 'http://127.0.0.1:8000/api'
const studyToken = 'boardgame-study-12345'
//let session_id = ''

type Participant = {
  participant_id: string
  study_group: string
}

const apiClient = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Enables sending cookies and CORS support
})

function newParticipant(): Promise<Participant> {
  return apiClient.post(`/auth/session`, { body: { token: studyToken } }).then((response) => {
    // session_id = response.headers['Set-Cookie'] || ''
    return response.data as Participant
  })
}

function getGames(query?: string): Promise<BoardGame[]> {
  return apiClient
    .get(`/games/`, { params: { q: query } })
    .then((response) => response.data.items as BoardGame[])
}

function getRecommendations(
  liked_games: BoardGame[],
  playercount: number,
): Promise<Recommendation[]> {
  const liked_game_ids = liked_games.map((game) => game.id)
  return apiClient
    .post(`/recommendations`, {
      body: {
        liked_game_ids: liked_game_ids,
        playercount: playercount,
      },
    })
    .then((response) => response.data as Recommendation[])
}

export { newParticipant, getGames, getRecommendations }
