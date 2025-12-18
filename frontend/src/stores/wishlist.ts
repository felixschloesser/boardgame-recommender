import type { Recommendation } from '../recommendation.mjs'
import { defineStore } from 'pinia'

export const useWishlistStore = defineStore('wishlist', {
  state: () => ({
    items: new Map<string, Recommendation[]>(),
  }),

  getters: {
    inWishlist: (state) => {
      return (sessionId: string, rec: Recommendation) =>
        state.items.get(sessionId)?.some((item) => item.boardgame.id === rec.boardgame.id) ?? false
    },

    recommendationsFor: (state) => {
      return (sessionId: string) => state.items.get(sessionId) ?? []
    },

    allItems: (state) => {
      return state.items
    },
  },

  actions: {
    add(sessionId: string, rec: Recommendation) {
      const list = this.items.get(sessionId) ?? []
      if (!list.some((item) => item.boardgame.id === rec.boardgame.id)) {
        this.items.set(sessionId, [...list, rec])
      }
    },

    remove(sessionId: string, rec: Recommendation) {
      const list = this.items.get(sessionId) ?? []
      this.items.set(
        sessionId,
        list.filter((item) => item.boardgame.id !== rec.boardgame.id),
      )
    },

    clear() {
      this.items.clear()
    },
  },
})
