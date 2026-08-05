import { useUserStore } from '@/stores/user'

export function usePermission() {
  const userStore = useUserStore()

  function hasPermission(permission) {
    return userStore.hasPermission(permission)
  }

  function hasAnyPermission(permissions) {
    return permissions.some(p => userStore.hasPermission(p))
  }

  function hasAllPermissions(permissions) {
    return permissions.every(p => userStore.hasPermission(p))
  }

  return { hasPermission, hasAnyPermission, hasAllPermissions }
}