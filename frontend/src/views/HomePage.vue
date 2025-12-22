<script lang="ts" setup>
import { RouterLink } from 'vue-router'
import { computed } from 'vue'
import { useWishlistStore } from '@/stores/wishlist'

const wishlist = useWishlistStore()

const hasWishlist = computed(() => wishlist.allItems.size > 0)
</script>

<template>
  <div class="center container">
    <h1 class="title">Boardgame Recommender</h1>
    <div class="actions">
      <div class="action">
        <RouterLink v-if="hasWishlist" to="/wishlist">
          <button class="nav-button btn-primary">
            <Icon icon="material-symbols:favorite-rounded" width="20" height="20" />
            Wishlist
          </button>
        </RouterLink>
        <button v-else class="nav-button btn-primary" :disabled="true">
          <Icon icon="material-symbols:favorite-outline-rounded" width="20" height="20" />
          Wishlist
        </button>
      </div>
      <div class="action">
        <RouterLink to="/explore">
          <button class="nav-button btn-primary">
            <Icon icon="material-symbols:explore-rounded" width="20" height="20" />
            Explore
          </button>
        </RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.title {
  font-size: var(--text-2xl);
  margin: var(--space-5) 0 var(--space-6);
  text-align: center;
  font-weight: 800;
  letter-spacing: 0.2px;
}

.nav-button {
  margin: var(--space-2);
  padding: var(--space-2) var(--space-3);
  min-width: 140px;
  height: 40px;
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font-size: var(--text-lg);
}

.actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
}

@media (min-width: 768px) {
  .actions {
    flex-direction: row;
  }
}

a {
  text-decoration: none;
}

.center {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 100vh;
}
</style>
