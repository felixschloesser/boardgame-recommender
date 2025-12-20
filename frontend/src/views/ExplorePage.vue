<script lang="ts" setup>
import { RouterLink, useRouter } from 'vue-router'
import { onMounted, ref } from 'vue'
import GameAdder from '@/components/GameAdder.vue'
import type { Option } from '@/boardGame.mjs'
import type { Preferences } from '@/api.mts'
import * as api from '@/api.mjs'
import { formatApiError } from '@/api.mjs'
import type BoardGame from '@/boardGame.mjs'

interface Props {
  id?: string // id can be undefined if not passed as a prop
}

const props = defineProps<Props>()
const router = useRouter()

const games = ref<Option[]>([])
const earlierPreferences = ref<Preferences | undefined>(undefined)
const errorMessage = ref<string | null>(null)

const gameAdderRef = ref<InstanceType<typeof GameAdder>>()
const playerCount = ref(4)

const loading = ref(false)

const clampPlayers = () => {
  if (!playerCount.value || playerCount.value < 1) playerCount.value = 1
}

// Select the entire number when interacting with the players input so typing replaces it
const selectAll = (e: Event) => {
  const el = e.target as HTMLInputElement | null
  if (el && typeof el.select === 'function') {
    // Delay selection very slightly to ensure it applies after focus/click
    requestAnimationFrame(() => el.select())
  }
}

onMounted(async () => {
  try {
    const gameObj: BoardGame[] = await api.getGames()
    const gamesToAdd = gameObj.map((game) => ({
      id: game.id,
      name: game.title,
    }))
    games.value.push(...gamesToAdd)
    // fetch earlier preferences if id is provided
    await fetchEarlierPreferences()
  } catch (error) {
    errorMessage.value = formatApiError(error)
  }
})

const fetchEarlierPreferences = async () => {
  if (props.id) {
    earlierPreferences.value = await api.getSessionPreferences(props.id)
    gameAdderRef.value?.addedGames.splice(0, gameAdderRef.value?.addedGames.length) // Clear current added games
    gameAdderRef.value?.addedGames.push(...earlierPreferences.value.liked_games)
    playerCount.value = earlierPreferences.value.players
  }
}

const confirm = async () => {
  if (gameAdderRef.value?.addedGames && gameAdderRef.value.addedGames.length > 0) {
    errorMessage.value = null
    loading.value = true // start loading state
    // get the selected games from the gameAdder component
    const selectedGames: Option[] = gameAdderRef.value.addedGames
    // fetch recommendations & redirect
    try {
      const id = await api.getRecommendations({
        liked_games: selectedGames,
        players: playerCount.value,
      })
      router.push({ path: `/recommendations/${id}` })
    } catch (error) {
      errorMessage.value = formatApiError(error)
    } finally {
      loading.value = false // stop loading state
    }
  }
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><Icon class="icon-btn" icon="material-symbols:home-rounded" /></RouterLink>
    <RouterLink to="/wishlist"
      ><Icon class="icon-btn" icon="material-symbols:favorite-rounded"
    /></RouterLink>
  </nav>
  <h1 class="header">Enter games you already tried and liked here:</h1>
  <h2 class="subheader">You can add multiple games to get better recommendations.</h2>
  <p v-if="errorMessage" class="error-banner" role="alert">
    <Icon icon="mdi:alert-circle" class="icon-alert" />
    {{ errorMessage }}
  </p>
  <GameAdder ref="gameAdderRef" :options="games" />
  <h1 class="header">Enter preferred number of players:</h1>
  <div class="players-control card">
    <button
      class="players-btn btn-outline"
      aria-label="Decrease players"
      @click="playerCount = Math.max(1, playerCount - 1)"
    >
      <Icon icon="mdi:chevron-left" width="28" height="28" />
    </button>
    <div class="players-display">
      <Icon icon="mdi:account-group" class="icon-players" />
      <input
        class="players-input"
        type="number"
        inputmode="numeric"
        min="1"
        v-model.number="playerCount"
        @focus="selectAll"
        @click="selectAll"
        @mouseup.prevent
        @blur="clampPlayers"
        aria-label="Number of players"
      />
    </div>
    <button
      class="players-btn btn-outline"
      aria-label="Increase players"
      @click="playerCount = playerCount + 1"
    >
      <Icon icon="mdi:chevron-right" width="28" height="28" />
    </button>
  </div>

  <button
    class="btn-confirm btn-primary"
    @click="confirm"
    :disabled="loading || !gameAdderRef?.addedGames || gameAdderRef.addedGames.length < 1"
    :aria-busy="loading ? 'true' : 'false'"
  >
    <template v-if="loading">
      <Icon class="spin" icon="material-symbols:progress-activity" width="20" height="20" />
      Finding recommendations…
    </template>
    <template v-else>
      Get Recommendations <Icon icon="material-symbols:arrow-forward-rounded" />
    </template>
  </button>
  <div v-if="loading" class="loading-overlay"></div>
</template>

<style scoped>
.header {
  font-size: var(--text-xl);
  margin: var(--space-4) 0;
  text-align: center;
}

.subheader {
  font-size: var(--text-md);
  margin: 0 0 var(--space-4) 0;
  text-align: center;
  color: var(--color-text-secondary);
}

.icon-players {
  cursor: auto;
  width: 28px;
  height: 28px;
  color: var(--color-text);
}

/* removed modal loading styles; loading now indicated on button */

.players-control {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3);
  width: 100%;
  max-width: 300px;
  margin: 0 auto var(--space-4);
}

.players-btn {
  border-radius: var(--radius-md);
  width: 48px;
  height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.players-display {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  flex: 1 1 auto;
  justify-content: center;
}

.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 1000;
  pointer-events: auto;
  cursor: wait;
}

.players-input {
  width: 56px;
  text-align: center;
  font-size: var(--text-xl);
  font-weight: 700;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text);
  -moz-appearance: textfield;
}

/* Hide number input spinners in Chrome/Safari/Edge/Opera */
.players-input::-webkit-outer-spin-button,
.players-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.btn-confirm {
  display: flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  margin: var(--space-3) auto;
  padding: var(--space-3) var(--space-4);
  font-size: var(--text-md);
  gap: var(--space-2);
}

.error-banner {
  margin: 0 auto var(--space-4);
  padding: var(--space-3);
  max-width: 640px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  border-radius: var(--radius-md);
  background: #ffe8e6;
  color: #8b1b0f;
  border: 1px solid #f5c6c2;
}

.icon-alert {
  width: 20px;
  height: 20px;
}

/* Spinner styles moved to global theme.css (.spin utility) */

.btn-confirm:disabled {
  /* styles handled by .btn-primary:disabled */
}

.btn-confirm :deep(svg) {
  margin-left: var(--space-2);
}
</style>
