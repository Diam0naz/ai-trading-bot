import Database from 'better-sqlite3'
import path from 'path'

const DB_PATH = process.env.DATABASE_PATH

if (!DB_PATH) {
  throw new Error('DATABASE_PATH env var is not set in .env.local')
}

declare global {
  // eslint-disable-next-line no-var
  var __db: Database.Database | undefined
}

function getDb(): Database.Database {
  if (!global.__db) {
    global.__db = new Database(path.resolve(DB_PATH!), { readonly: true })
    global.__db.pragma('journal_mode = WAL')
  }
  return global.__db
}

export default getDb
