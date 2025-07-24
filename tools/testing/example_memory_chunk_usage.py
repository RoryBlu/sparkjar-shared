#!/usr/bin/env python3

import logging
logger = logging.getLogger(__name__)

"""
Example of how to use the memory tool's process_text_chunk capability
in a CrewAI agent.

This shows the pattern for processing various types of text:
- Meeting notes
- Email threads  
- Document pages
- Spreadsheet data
"""

from services.crew_api.src.tools.sj_memory_tool import SJMemoryTool

# Example 1: Processing Meeting Notes
def process_meeting_notes():
    """Example of processing meeting notes."""
    
    # Initialize the tool
    memory_tool = SJMemoryTool(client_user_id="client-001")
    
    # Meeting notes text
    meeting_notes = """
    Meeting: Q1 Product Launch Planning
    Date: March 10, 2025
    Attendees: John Smith (Product Manager), Sarah Chen (CTO), Mike Johnson (Sales VP)
    
    Key Decisions:
    - Launch date set for April 15th
    - Sarah's team will complete API v2 by March 25th
    - Mike needs 50 demo accounts for sales team training
    - Budget approved: $2.5M for marketing campaign
    
    Action Items:
    - John: Finalize feature list by March 12th
    - Sarah: Deploy staging environment by March 20th
    - Mike: Schedule sales training for April 1-5
    
    Risks Discussed:
    - Competitor launching similar product in May
    - Need to hire 3 more engineers for post-launch support
    """
    
    # Process with the memory tool
    result = memory_tool._run(
        operation="process_text_chunk",
        text=meeting_notes,
        source="meeting_notes_Q1_planning",
        actor_type="meeting_assistant",
        actor_id="bot-001"
    )
    
    return result

# Example 2: Processing Email Thread
def process_email_thread():
    """Example of processing an email conversation."""
    
    memory_tool = SJMemoryTool(client_user_id="client-001")
    
    email_thread = """
    From: david.wilson@techcorp.com
    To: jennifer.lopez@sparkjar.com
    Subject: Re: Partnership Proposal
    
    Hi Jennifer,
    
    Thanks for sending over the partnership proposal. I've reviewed it with our 
    executive team, including our CEO Mary Johnson and CFO Robert Zhang.
    
    We're very interested in moving forward with the integration between your 
    SparkJAR platform and our TechFlow ERP system. The AI-powered automation 
    features would be a game-changer for our 5,000+ enterprise customers.
    
    Robert has approved a pilot program budget of $500K for Q2. Mary wants to 
    see a demo specifically focused on supply chain optimization use cases.
    
    Can we schedule a technical deep-dive for next Tuesday at 2 PM PST?
    
    Best regards,
    David Wilson
    VP of Strategic Partnerships
    TechCorp Inc.
    """
    
    result = memory_tool._run(
        operation="process_text_chunk",
        text=email_thread,
        source="email_partnership_techcorp",
        actor_type="email_processor",
        actor_id="bot-002"
    )
    
    return result

# Example 3: Processing Spreadsheet Data (as text)
def process_spreadsheet_excerpt():
    """Example of processing data extracted from a spreadsheet."""
    
    memory_tool = SJMemoryTool(client_user_id="client-001")
    
    # This would come from spreadsheet parsing
    spreadsheet_text = """
    Echelon Industries - Q4 2024 Estimates
    
    Project: Downtown Tower Complex
    Client: Mercy Hospital System
    Project Manager: Carlos Rodriguez
    Lead Estimator: Amanda Foster
    
    Phase 1 - Foundation and Structure
    - Excavation: $2.3M (Subcontractor: DeepDig LLC)
    - Concrete: $4.7M (Supplier: ReadyMix Partners) 
    - Steel framing: $8.2M (Supplier: SteelCo International)
    - Timeline: 6 months starting May 2025
    
    Phase 2 - MEP Systems  
    - Electrical: $3.5M (Subcontractor: PowerGrid Solutions)
    - Plumbing: $2.8M (Subcontractor: FlowMaster Inc)
    - HVAC: $4.1M (Subcontractor: Climate Control Systems)
    - Timeline: 4 months starting November 2025
    
    Total Estimate: $25.6M
    Contingency: 15% ($3.84M)
    """
    
    result = memory_tool._run(
        operation="process_text_chunk",
        text=spreadsheet_text,
        source="echelon_estimates_Q4_2024",
        actor_type="spreadsheet_processor",
        actor_id="bot-003"
    )
    
    return result

# Example 4: Processing Handwritten Memoir Page
def process_memoir_page():
    """Example of processing a page from Le Baron's memoir."""
    
    memory_tool = SJMemoryTool(client_user_id="client-001")
    
    # This would come from OCR of handwritten pages
    memoir_text = """
    Page 47 - Spring of 1972
    
    The meeting with Colonel Ramirez changed everything. He introduced me to 
    his associate, a quiet man named Eduardo Mendez who ran the logistics 
    through his company, Transporte del Sur. 
    
    Mendez had connections in Miami - specifically with the Delgado brothers 
    who owned several import businesses. Their legitimate front was a chain 
    of electronics stores called TechImport USA.
    
    By June, we had established the route: Bogotá → Panama City → Miami. 
    The pilot was an American named Jack Morrison, former Air Force, who 
    flew a modified Cessna 310. Each flight carried 500 kilos hidden in 
    false compartments.
    
    The first successful run was June 15, 1972. I remember because it was 
    my daughter Isabella's 5th birthday. The irony wasn't lost on me - 
    securing her future through such dangerous means.
    
    Ramirez took 30%, Mendez handled logistics for 20%, Morrison got $50K 
    per flight, and the Delgados managed distribution for 25%. That left 
    25% for me - roughly $2M per shipment at street value.
    """
    
    result = memory_tool._run(
        operation="process_text_chunk",
        text=memoir_text,
        source="lebaron_memoir_page_47",
        actor_type="memoir_processor",
        actor_id="bot-004"
    )
    
    return result

# Example 5: Agent Using Memory Tool in Task
def example_agent_code():
    """Example of how an agent would use this in a task."""
    
    example_code = '''
    # In your CrewAI agent task:
    
    agent = Agent(
        role="Document Processor",
        goal="Extract and store knowledge from documents",
        tools=[memory_tool],
        backstory="You excel at understanding documents and extracting actionable intelligence."
    )
    
    task = Task(
        description="""
        Process this document and extract all relevant information:
        
        {document_text}
        
        Use the memory tool's process_text_chunk operation to:
        1. Extract all people, organizations, and concepts
        2. Identify relationships between entities  
        3. Store observations and facts
        4. Let the tool search for related context automatically
        
        The operation to use is:
        memory_tool._run(
            operation="process_text_chunk",
            text=<the document text>,
            source=<document identifier>,
            actor_type="agent",
            actor_id=<your agent id>
        )
        """,
        agent=agent
    )
    '''
    
    return example_code

if __name__ == "__main__":
    logger.info("Memory Tool Chunk Processing Examples")
    logger.info("=" * 60)
    
    # Show example usage patterns
    logger.info("\n1. Meeting Notes Example:")
    logger.info("   - Extracts attendees, decisions, action items, dates")
    logger.info("   - Creates timeline events")
    logger.info("   - Links people to responsibilities")
    
    logger.info("\n2. Email Thread Example:")
    logger.info("   - Identifies companies and people")
    logger.info("   - Extracts deal terms and budgets")
    logger.info("   - Captures meeting requests")
    
    logger.info("\n3. Spreadsheet Data Example:")
    logger.info("   - Extracts project hierarchies")
    logger.info("   - Identifies contractors and suppliers")
    logger.info("   - Captures financial figures with context")
    
    logger.info("\n4. Memoir Page Example:")
    logger.info("   - Maintains character relationships over time")
    logger.info("   - Tracks events with dates")
    logger.info("   - Preserves narrative context")
    
    logger.info("\n5. Agent Integration:")
    logger.info(example_agent_code())
    
    logger.info("\nThe beauty of this system: Each chunk builds on all previous memory!")
    logger.info("The memory graph becomes the unlimited context window.")