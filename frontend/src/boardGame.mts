export default interface BoardGame {
  id: number
  title: string
  description: string
  mechanics: string[]
  genre: string[]
  themes: string[]
  min_players: number
  max_players: number
  complexity: number
  age_recommendation: number
  num_user_ratings: number
  avg_user_rating: number
  year_published: number
  playing_time_minutes: number
  image_url: string
  bgg_url: string
}

export interface Option {
  id: number
  name: string
}
