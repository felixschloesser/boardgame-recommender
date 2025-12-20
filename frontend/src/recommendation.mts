'recommendations'
import type BoardGame from './boardGame.mjs'

interface FeatureExplanation {
  label: string
  category: string
  influence: 'positive' | 'negative' | 'neutral'
}

interface ReferencesExplanation {
  bgg_id: number
  title: string
  influence: 'positive' | 'negative' | 'neutral'
}

export interface Recommendation {
  id?: string
  boardgame: BoardGame
  explanation: {
    type: 'references' | 'features'
    references?: ReferencesExplanation[] | null
    features?: FeatureExplanation[] | null
  }
}
