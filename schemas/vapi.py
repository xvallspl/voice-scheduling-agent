"""Vapi request and response schemas.

This module defines Pydantic models for Vapi webhook payloads,
including tool call lists, function arguments, and responses.
"""

from pydantic import BaseModel, Field, field_validator

from schemas.calendar import EventCreate


class ToolCallFunction(BaseModel):
    """Function call details within a tool call.

    Contains the function name and arguments as provided by Vapi.
    Arguments are strictly validated against the expected schema.
    """

    name: str = Field(
        ...,
        description="Function name to invoke",
    )
    arguments: EventCreate = Field(
        ...,
        description="Arguments for calendar event creation (name, date, time, optional title)",
    )


class ToolCallItem(BaseModel):
    """Individual tool call item in the toolCallList.

    Represents a single function invocation request from Vapi.
    """

    id: str = Field(
        ...,
        min_length=1,
        description="Unique identifier for this tool call",
    )
    function: ToolCallFunction = Field(
        ...,
        description="Function to be invoked",
    )


class VapiRequestMessage(BaseModel):
    """Message wrapper containing tool call list.

    The top-level structure of a Vapi webhook request.
    """

    toolCallList: list[ToolCallItem] = Field(
        default_factory=list,
        description="List of tool calls to process",
    )


class VapiRequest(BaseModel):
    """Complete Vapi webhook request payload.

    Root model for incoming Vapi webhook requests.
    """

    message: VapiRequestMessage = Field(
        ...,
        description="Message containing tool calls",
    )

    @field_validator("message")
    @classmethod
    def validate_tool_call_list_not_empty(
        cls, v: VapiRequestMessage
    ) -> VapiRequestMessage:
        """Ensure toolCallList is not empty.

        Args:
            v: The message to validate

        Returns:
            VapiRequestMessage: Validated message

        Raises:
            ValueError: If toolCallList is empty
        """
        if not v.toolCallList:
            raise ValueError("toolCallList cannot be empty")
        return v


class VapiResult(BaseModel):
    """Result for a single tool call.

    Response format for an individual function invocation result.
    """

    toolCallId: str = Field(
        ...,
        min_length=1,
        description="ID of the tool call this result is for",
    )
    result: str = Field(
        ...,
        min_length=1,
        description="Result message for the voice agent",
    )


class VapiResponse(BaseModel):
    """Complete Vapi webhook response.

    Root model for outgoing Vapi webhook responses.
    """

    results: list[VapiResult] = Field(
        default_factory=list,
        description="List of results for each tool call",
    )
