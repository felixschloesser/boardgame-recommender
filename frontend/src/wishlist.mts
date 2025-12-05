import type { Recommendation } from './recommendation.mjs'

let wishlist: Recommendation[] = []

function addRecommendationToWishlist(recommendation: Recommendation) {
  if (!wishlist.find((item) => item.boardgame.id === recommendation.boardgame.id)) {
    wishlist.push(recommendation)
  }
}

function getWishlist(): Recommendation[] {
  return wishlist
}

function clearWishlist() {
  wishlist = []
}

function inWishlist(recommendation: Recommendation): boolean {
  return !!wishlist.find((item) => item.boardgame.id === recommendation.boardgame.id)
}

export { addRecommendationToWishlist, getWishlist, clearWishlist, inWishlist }
