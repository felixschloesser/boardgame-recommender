<script lang="ts" setup>
import { RouterLink, useRouter } from 'vue-router'
import { onMounted, ref } from 'vue'
import GameAdder from '@/components/GameAdder.vue'
import type { Option } from '@/boardGame.mjs'
import type { Preferences } from '@/api.mts'
import * as api from '@/api.mjs'
import type BoardGame from '@/boardGame.mjs'

interface Props {
  id?: string // id can be undefined if not passed as a prop
}

const props = defineProps<Props>()
const router = useRouter()
const games = ref<Option[]>([])
const earlierPreferences = ref<Preferences | undefined>(undefined)

const addedGames = ref<Option[]>([])
const playerCount = ref(4)

onMounted(async () => {
  const gameObj: BoardGame[] = await api.getGames()
  const gamesToAdd = gameObj.map((game) => ({
    id: game.id,
    name: game.title,
  }))
  games.value.push(...gamesToAdd)
  // fetch earlier preferences if id is provided
  await fetchEarlierPreferences()
})

const fetchEarlierPreferences = async () => {
  if (props.id) {
    earlierPreferences.value = await api.getSessionPreferences(props.id)
    addedGames.value.splice(0, addedGames.value.length) // Clear current added games
    addedGames.value.push(...earlierPreferences.value.liked_games)
    playerCount.value = earlierPreferences.value.players
  }
}

const confirm = async () => {
  if (addedGames.value) {
    // get the selected games from the gameAdder component
    const selectedGames: Option[] = addedGames.value
    // fetch recommendations & redirect
    await api
      .getRecommendations({ liked_games: selectedGames, players: playerCount.value })
      .then((id) => router.push({ path: `/recommendations/${id}` }))
  }
}
</script>

<template>
  <nav class="navbar">
    <RouterLink to="/"><img src="../assets/home.svg" alt="Home" class="icon" /></RouterLink
    ><RouterLink to="/wishlist"
      ><img src="../assets/wishlist.svg" alt="Wishlist" class="icon"
    /></RouterLink>
  </nav>
  <h1 class="header">Enter games you already tried and liked here:</h1>
  <GameAdder
    @addGame="(game) => addedGames.push(game)"
    @removeGame="
      (game) => {
        addedGames = addedGames.filter((g) => g.id !== game.id)
      }
    "
    :options="games"
    :preAdded="addedGames"
  />
  <h1 class="header">Enter preferred number of players:</h1>
  <div class="players">
    <img src="../assets/players.svg" alt="Players" class="icon-players" /><input
      class="input-players"
      type="number"
      min="1"
      v-model="playerCount"
    />
  </div>

  <button class="btn-confirm" @click="confirm" :disabled="!addedGames || addedGames.length < 1">
    Get Recommendations <img src="../assets/continue_arrow.svg" alt="Arrow Right" />
  </button>
</template>

<style scoped>
.header {
  font-size: 24px;
  margin: 16px 0;
  text-align: center;
}

.icon-players {
  cursor: auto;
  width: 35px;
  height: 35px;
  padding: 10px;
}

.players {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.input-players {
  border-radius: 8px;
  border: black 2px solid;
  padding: 8px;
  font-size: 16px;
  width: 60px;
  text-align: center;
}

.btn-confirm {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  padding: 8px 16px;
  font-size: 16px;
  background-color: #4caf50;
  color: white;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.btn-confirm:disabled {
  background-color: gray;
  color: white;
  cursor: not-allowed;
}

.btn-confirm img {
  margin-left: 8px; /* Add some space between text and icon */
  filter: invert(1); /* Invert icon color to white */
}
</style>
