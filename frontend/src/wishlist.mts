import type { Recommendation } from './recommendation.mjs'

let wishlist: Map<string, Recommendation[]> = new Map()

function addRecommendationToWishlist(reccomendationId: string, recommendation: Recommendation) {
  if (!wishlist.has(reccomendationId)) {
    wishlist.set(reccomendationId, [recommendation])
  } else {
    const recommendations = wishlist.get(reccomendationId)!
    if (!recommendations.find((item) => item.boardgame.id === recommendation.boardgame.id)) {
      recommendations.push(recommendation)
    }
  }
}

function removeRecommendationFromWishlist(
  recommendationId: string,
  recommendation: Recommendation,
) {
  if (!wishlist.has(recommendationId)) {
    return
  } else {
    const recommendations = wishlist.get(recommendationId)!
    wishlist.set(
      recommendationId,
      recommendations.filter((item) => item.boardgame.id !== recommendation.boardgame.id),
    )
    return
  }
}

function getWishlist(): Map<string, Recommendation[]> {
  return wishlist
}

function getRecommendationsForId(reccomendationId: string): Recommendation[] {
  return wishlist.get(reccomendationId) || []
}

function clearWishlist() {
  wishlist = new Map()
}

function inWishlist(reccomendationId: string, recommendation: Recommendation): boolean {
  if (!wishlist.has(reccomendationId)) {
    return false
  }
  const recommendations = wishlist.get(reccomendationId)!
  return recommendations.includes(recommendation)
}

export {
  addRecommendationToWishlist,
  getWishlist,
  clearWishlist,
  inWishlist,
  removeRecommendationFromWishlist,
  getRecommendationsForId,
}
