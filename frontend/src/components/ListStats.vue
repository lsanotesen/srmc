<template>
  <div class="list-stats">
    <span v-for="(item, index) in items" :key="item.key || index" class="list-stats__item">
      <span v-if="index" class="list-stats__sep">·</span>
      <span class="list-stats__label">{{ item.label }}</span>
      <span class="list-stats__value">{{ item.value }}</span>
    </span>
  </div>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
/* 紧凑文字统计：不占用大块区域，随主题切换颜色 */
.list-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 6px;
  margin-bottom: 12px;
  font-size: 13px;
  line-height: 20px;
  color: var(--app-text-2);
}

.list-stats__item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.list-stats__sep {
  color: var(--app-text-3);
  margin-right: 2px;
}

.list-stats__label {
  color: var(--app-text-2);
}

.list-stats__value {
  color: var(--app-text);
  font-weight: 600;
}
</style>
