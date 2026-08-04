import { faker } from '@faker-js/faker'

class User {
    constructor() {
        this.id = faker.string.uuid()
        this.name = faker.person.fullName()
        this.avatar = faker.image.avatar()
        this.phone = faker.phone.number('+1##########')
    }
}
export class Message {
    constructor(isMainUser, msg, date) {
        this.id = faker.string.uuid()
        this.msg = msg || faker.lorem.words({ min: 1, max: 20 })
        this.isMainUser = isMainUser
        this.date = date || faker.date.recent()
    }
}

export const mainUser = new User()

export const contacts = [...Array(15).keys()].map(() => new User())

export const agentContact = new User()
agentContact.name = 'AI Agent'
agentContact.avatar = 'https://i.pravatar.cc/150?img=12'
agentContact.id = 'agent-001'

export const contactsMessages = [
    ...contacts.map((contact) => ({
        contact,
        messages: [...Array(50).keys()]
            .map((_, i) => {
                return (i + 1) % 2 === 0 ? new Message(true) : new Message(false)
            })
            .filter((m) => m.msg),
    })),
    { contact: agentContact, messages: [] },
]
