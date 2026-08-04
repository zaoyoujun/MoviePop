import { cpSync, existsSync, mkdirSync, readdirSync, writeFileSync } from 'fs'
import { dirname, join } from 'path'

export const directoryHasData = (directory) => {
  try {
    return existsSync(directory) && readdirSync(directory).length > 0
  } catch {
    return false
  }
}

const copyDirectoryContents = (sourceDirectory, targetDirectory, force = true) => {
  mkdirSync(targetDirectory, { recursive: true })

  for (const entry of readdirSync(sourceDirectory, { withFileTypes: true })) {
    cpSync(join(sourceDirectory, entry.name), join(targetDirectory, entry.name), {
      recursive: entry.isDirectory(),
      force,
      errorOnExist: !force,
    })
  }
}

const backupTargetDirectory = (targetDirectory, backupRoot, label) => {
  if (!directoryHasData(targetDirectory)) return null

  const backupDirectory = join(backupRoot, `${label}-${Date.now()}`)
  mkdirSync(backupRoot, { recursive: true })
  cpSync(targetDirectory, backupDirectory, {
    recursive: true,
    force: false,
    errorOnExist: true,
  })
  return backupDirectory
}

const copyBackendUserData = (sourceDirectory, targetDirectory) => {
  for (const directoryName of ['data', 'covers', 'static']) {
    const sourceSubdirectory = join(sourceDirectory, directoryName)
    if (existsSync(sourceSubdirectory)) {
      copyDirectoryContents(sourceSubdirectory, join(targetDirectory, directoryName))
    }
  }
}

export const migrateUserDataWhenTargetMissing = ({ sourceDirectory, targetDirectory }) => {
  if (!directoryHasData(sourceDirectory) || directoryHasData(targetDirectory)) {
    return { migrated: false, reason: 'not-needed' }
  }

  try {
    cpSync(sourceDirectory, targetDirectory, {
      recursive: true,
      force: false,
      errorOnExist: true,
    })
    return { migrated: true }
  } catch (error) {
    console.warn(`Failed to migrate MoviePop application data: ${error.message}`)
    return { migrated: false, reason: 'failed' }
  }
}

export const migrateBackendDataWhenTargetMissing = ({ sourceDirectory, targetDirectory, backupRoot }) => {
  const sourceDatabase = join(sourceDirectory, 'data', 'library.db')
  const targetDatabase = join(targetDirectory, 'data', 'library.db')

  if (!existsSync(sourceDatabase) || existsSync(targetDatabase)) {
    return { migrated: false, reason: 'not-needed' }
  }

  try {
    const backupDirectory = backupTargetDirectory(targetDirectory, backupRoot, 'before-app-data-migration')
    copyBackendUserData(sourceDirectory, targetDirectory)
    return { migrated: true, backupDirectory }
  } catch (error) {
    console.warn(`Failed to move MoviePop backend data from the previous location: ${error.message}`)
    return { migrated: false, reason: 'failed' }
  }
}

export const migrateLegacyBackendData = ({ legacyDirectory, targetDirectory, backupRoot }) => {
  const legacyDatabase = join(legacyDirectory, 'data', 'library.db')
  const markerPath = join(dirname(legacyDirectory), '.moviepop-legacy-migrated')

  if (!existsSync(legacyDatabase) || existsSync(markerPath)) {
    return { migrated: false, reason: 'not-needed' }
  }

  try {
    const backupDirectory = backupTargetDirectory(targetDirectory, backupRoot, 'before-legacy-migration')
    copyBackendUserData(legacyDirectory, targetDirectory)

    writeFileSync(markerPath, new Date().toISOString(), 'utf8')
    return { migrated: true, backupDirectory }
  } catch (error) {
    console.warn(`Failed to migrate legacy MoviePop backend data: ${error.message}`)
    return { migrated: false, reason: 'failed' }
  }
}
