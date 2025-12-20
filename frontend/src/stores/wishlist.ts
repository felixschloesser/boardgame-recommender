import type { Recommendation } from '../recommendation.mjs'
import { defineStore } from 'pinia'

export const useWishlistStore = defineStore('wishlist', {
  state: () => ({
    items: new Map<string, Recommendation[]>(), // map from sessionId to list of recommendations
    taskCompleted: new Map<string, boolean>(),
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

    hasCompletedTask: (state) => {
      return (sessionId: string) => state.taskCompleted.get(sessionId) ?? false
    },

    wishListCount: (state) => {
      return (sessionId: string) => state.items.get(sessionId)?.length ?? 0
    },
  },

  actions: {
    // sessionId: is the recommendation ID
    // recommendation should include recId
    add(sessionId: string, rec: Recommendation) {
      const list = this.items.get(sessionId) ?? []
      if (!list.some((item) => item.boardgame.id === rec.boardgame.id)) {
        const updated = [...list, rec]
        this.items.set(sessionId, updated)

        if (updated.length >= 2) {
          this.taskCompleted.set(sessionId, true)
        }
      }
    },
    // sessionId: is the recommendation ID
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
