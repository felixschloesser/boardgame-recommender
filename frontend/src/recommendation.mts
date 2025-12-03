'recommendations'
import type BoardGame from './BoardGame.mts'

export interface Recommendation {
  boardgame: BoardGame
  explanation: {
    references: string[]
    features: string[]
  }
}
