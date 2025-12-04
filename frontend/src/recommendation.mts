'recommendations'
import type BoardGame from './boardGame.mjs'

export interface Recommendation {
  boardgame: BoardGame
  explanation: {
    references: string[]
    features: string[]
  }
}
