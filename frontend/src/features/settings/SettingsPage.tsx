import { useState } from 'react'
import { ProfileSection } from './components/ProfileSection'
import { AccountsSection } from './components/AccountsSection'

type Tab = 'profile' | 'accounts'

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<Tab>('profile')

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-xl font-semibold text-text-primary">Settings</h1>

      <div role="tablist" aria-label="Settings sections" className="flex gap-1 border-b border-border">
        <button
          role="tab"
          type="button"
          aria-selected={activeTab === 'profile'}
          aria-controls="panel-profile"
          id="tab-profile"
          onClick={() => setActiveTab('profile')}
          className={`px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 ${
            activeTab === 'profile'
              ? 'border-b-2 border-primary text-primary'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          Profile
        </button>
        <button
          role="tab"
          type="button"
          aria-selected={activeTab === 'accounts'}
          aria-controls="panel-accounts"
          id="tab-accounts"
          onClick={() => setActiveTab('accounts')}
          className={`px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary/50 ${
            activeTab === 'accounts'
              ? 'border-b-2 border-primary text-primary'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          Accounts
        </button>
      </div>

      <div
        id="panel-profile"
        role="tabpanel"
        aria-labelledby="tab-profile"
        hidden={activeTab !== 'profile'}
      >
        <ProfileSection />
      </div>
      <div
        id="panel-accounts"
        role="tabpanel"
        aria-labelledby="tab-accounts"
        hidden={activeTab !== 'accounts'}
      >
        <AccountsSection />
      </div>
    </div>
  )
}
