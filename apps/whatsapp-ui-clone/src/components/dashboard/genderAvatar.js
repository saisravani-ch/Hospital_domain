// Heuristic gender inference for doctor names.
//
// The doctors table has no gender column, so we infer a likely gender from the
// name to pick a lady-doctor vs. man-doctor avatar. This is best-effort only:
// unknown names fall back to a neutral initials avatar.

// Common female first names (Indian + generic). Lowercase, no titles.
const FEMALE_NAMES = new Set([
    'priya', 'anjali', 'divya', 'shreya', 'sneha', 'pooja', 'neha', 'kavya',
    'lakshmi', 'lakshmy', 'meena', 'meenakshi', 'radha', 'rekha', 'geetha',
    'gita', 'sita', 'sunita', 'sunitha', 'anitha', 'anita', 'kavitha', 'kavita',
    'sushma', 'sushmita', 'deepa', 'deepika', 'nisha', 'asha', 'usha', 'uma',
    'padma', 'padmini', 'shanti', 'shantha', 'vidya', 'vidhya', 'maya', 'mala',
    'malathi', 'revathi', 'roja', 'saras', 'saraswathi', 'saraswati', 'suja',
    'sujatha', 'shobha', 'shobana', 'shalini', 'swati', 'swathi', 'jaya',
    'jayanthi', 'vasanthi', 'vani', 'veena', 'nandini', 'nandhini', 'bhavana',
    'bhavani', 'aishwarya', 'aarti', 'arti', 'aparna', 'archana', 'bhuvana',
    'chitra', 'gayathri', 'gayatri', 'harini', 'indira', 'indu', 'janani',
    'kalpana', 'kamala', 'keerthi', 'keerthana', 'kiran', 'manju', 'manjula',
    'megha', 'mythili', 'nithya', 'nisha', 'parvathi', 'parvathy', 'preethi',
    'preeti', 'ramya', 'ranjani', 'rashmi', 'rithika', 'ritika', 'sandhya',
    'sangeetha', 'sangeeta', 'shruthi', 'shruti', 'sindhu', 'sowmya', 'soumya',
    'sridevi', 'srividya', 'subhashini', 'thara', 'tara', 'vaishnavi',
    'vandana', 'varsha', 'vinodhini', 'yamini', 'yamuna', 'zara',
    // generic western
    'mary', 'sarah', 'sara', 'emma', 'olivia', 'sophia', 'isabella', 'mia',
    'emily', 'grace', 'anna', 'anne', 'laura', 'linda', 'susan', 'karen',
    'nancy', 'lisa', 'betty', 'helen', 'sandra', 'donna', 'ruth', 'sharon',
])

// Common male first names (used to override -a/-i suffix heuristic false hits).
const MALE_NAMES = new Set([
    'guru', 'prasad', 'ravi', 'raja', 'krishna', 'shiva', 'siva', 'ganesh',
    'ganesha', 'vishnu', 'hari', 'gopi', 'gopal', 'murali', 'bala', 'balaji',
    'surya', 'aditya', 'arjuna', 'karthika', 'sathya', 'satya', 'vidya',
    'ramanuja', 'narendra', 'rama', 'mahendra', 'chandra', 'indra', 'yudhistira',
])

// Titles that directly reveal gender.
const FEMALE_TITLES = ['mrs', 'ms', 'miss', 'smt', 'smt.']
const MALE_TITLES = ['mr', 'mr.', 'shri', 'sri']

function tokens(name) {
    return String(name || '')
        .replace(/\bdr\.?\b/gi, '')
        .replace(/\bprof\.?\b/gi, '')
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .map((t) => t.toLowerCase().replace(/[^a-z]/g, ''))
        .filter(Boolean)
}

// Returns 'female' | 'male' | 'neutral'.
export function inferGender(name) {
    const raw = String(name || '').toLowerCase()
    if (FEMALE_TITLES.some((t) => raw.includes(t + ' '))) return 'female'
    if (MALE_TITLES.some((t) => raw.includes(t + ' '))) return 'male'

    const parts = tokens(name)
    if (parts.length === 0) return 'neutral'

    // Explicit name-list checks across all tokens.
    for (const p of parts) {
        if (FEMALE_NAMES.has(p)) return 'female'
    }
    for (const p of parts) {
        if (MALE_NAMES.has(p)) return 'male'
    }

    // Suffix heuristic on the first (given) name: -a / -i / -priya endings
    // skew female in Indian naming, but only as a weak fallback.
    const first = parts[0]
    if (first.length >= 4 && /(a|i|ya|ika|itha|itha)$/.test(first)) return 'female'

    return 'neutral'
}

// Avatar descriptor: emoji + color for a doctor name.
export function doctorAvatar(name) {
    const g = inferGender(name)
    if (g === 'female') return { emoji: '👩‍⚕️', gender: 'female', color: '#f778ba' }
    if (g === 'male') return { emoji: '👨‍⚕️', gender: 'male', color: '#58a6ff' }
    return { emoji: '🩺', gender: 'neutral', color: '#8b949e' }
}
