<script lang="ts" setup>
import { ref } from 'vue'
import type { Recommendation } from '../recommendation.mjs'
import { addRecommendationToWishlist, inWishlist, removeRecommendationFromWishlist } from '../wishlist.mjs'

interface Props {
  recommendation: Recommendation
  explanationStyle: 'references' | 'features'
  size: 'small' | 'large'
}

const toggleWishList = () => {
  if (inWishlist(props.recommendation)) {
    // Already in wishlist, do nothing for 
    removeRecommendationFromWishlist(props.recommendation)
    isInWishlist.value = false
  } else {
    isInWishlist.value = true
    addRecommendationToWishlist(props.recommendation)
  }
}

defineEmits(['viewgame'])
const props = defineProps<Props>()

const isInWishlist = ref(inWishlist(props.recommendation))

</script>

<template>
  <div :class="`recommendation-card-${props.size}`">
    <div style="padding: 8px">
      <div class="game-image">
        <img :src="props.recommendation.boardgame.image_url" alt="Game image" />
      </div>
    </div>
    <div>
      <div :class="`game-title-${props.size}`">
        <h2>{{ props.recommendation.boardgame.title }}</h2>
        <div  @click="toggleWishList" v-if="props.size === 'large'" class="wishlist-button">
          <img v-if="isInWishlist" src="../assets/filled_heart.svg" alt="In Wishlist" />
          <img v-else src="../assets/heart.svg" alt="Wishlist" />
        </div>
        <div v-else>
          <div @click="$emit('viewgame', props.recommendation.boardgame.id)" class="redirect-arrow">
            <img src="../assets/arrow-right.svg" alt="View Game" />
          </div>
        </div>
      </div>
      <div class="explanation">
        <div v-if="props.explanationStyle === 'features'">
          <div
            :class="`explanation-tab-${feature.influence}`"
            v-for="feature in props.recommendation.explanation.features"
            :key="feature.label"
          >
            {{ feature.label }}
          </div>
        </div>
        <div v-else-if="props.explanationStyle === 'references'">
          <div
            :class="`explanation-tab-${reference.influence}`"
            v-for="reference in props.recommendation.explanation.references"
            :key="reference.bgg_id"
          >
            {{ reference.title }}
          </div>
        </div>
      </div>
      <div v-if="props.size === 'large'" class="redirect-arrow">
        <div @click="$emit('viewgame', props.recommendation.boardgame.id)">
            <img src="../assets/arrow-right.svg" alt="View Game" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommendation-card-large {
  border: 2px solid #000;
  border-radius: 8px;
  display: flex;
  flex-direction: row;
  width: 350px;
  padding: 16px;
  max-width: 400px;
  margin: 16px auto;
  box-shadow: 2px 2px 12px rgba(0, 0, 0, 0.1);
}

.wishlist-button {
  cursor: pointer;
}

.recommendation-card-small {
  border: 2px solid #000;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  width: 150px;
  padding: 16px;
  margin: 16px auto;
  box-shadow: 2px 2px 12px rgba(0, 0, 0, 0.1);
}

.game-title-large {
  display: flex;
  justify-content: space-between;
  width: 180px;
  align-items: center;
}

.game-title-small {
  display: flex;
  justify-content: space-between;
  width: 150px;
  align-items: center;
}

.redirect-arrow {
  display: flex;
  justify-content: flex-end;
  width: 100%;
}

.explanation-tab-neutral {
  background-color: #a2a6d0;
  border: 1px solid #002bd5;
  border-radius: 4px;
  padding: 3px 6px;
  margin: 4px;
}

.explanation-tab-positive {
  background-color: #a0d6a0;
  border: 1px solid #008000;
  border-radius: 4px;
  padding: 3px 6px;
  margin: 4px;
}

.explanation-tab-negative {
  background-color: #d0a0a0;
  border: 1px solid #ff0000;
  border-radius: 4px;
  padding: 3px 6px;
  margin: 4px;
}

.explanation {
  display: flex;
  flex-wrap: wrap;
  align-items: flex;
}

.game-image img {
  width: 150px;
  height: 150px;
}

.redirect-arrow {
  cursor: pointer;
}
</style>
